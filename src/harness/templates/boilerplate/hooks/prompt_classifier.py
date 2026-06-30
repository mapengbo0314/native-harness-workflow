import os
import sys

if os.environ.get("HARNESS_INTERNAL_LLM_CALL") == "1":
    sys.exit(0)

import sys
import json
import os
import logging
from pathlib import Path
from hook_common import resolve_project_root, resolve_plugin_root

# Load project .env files before Langfuse initializes its client.
# The platform CLI sets CLAUDE_PLUGIN_ROOT / GEMINI_PLUGIN_ROOT before
# the hook subprocess starts, so resolve_plugin_root() works here at
# module load time — before any langfuse import.
def _bootstrap_env():
    try:
        from dotenv import load_dotenv
        candidate = resolve_plugin_root()
        # Walk upward until we find a directory that has .env or .env.telemetry-harness.
        # Claude plugin root is two levels deep (.claude/harness-wf-plugin/); Gemini is one
        # level deep (.gemini/) — hardcoding parent depth breaks one of them.
        for _ in range(4):
            if (candidate / ".env").exists() or (candidate / ".env.telemetry-harness").exists():
                load_dotenv(candidate / ".env", override=False)
                load_dotenv(candidate / ".env.telemetry-harness", override=False)
                return
            candidate = candidate.parent
    except Exception:
        pass

_bootstrap_env()

try:
    from langfuse import observe
except ImportError:
    try:
        from langfuse.decorators import observe
    except ImportError:
        def observe(*args, **kwargs):
            def decorator(func):
                return func
            if len(args) == 1 and callable(args[0]):
                return args[0]
            return decorator

def fallback_classify(prompt):
    """Keyword fallback classification.

    Phase 6a (review finding #1): prefers the SHARED table shipped in the
    plugin's runtime slice (src/fallback_keywords.py) so this fallback can
    never drift from the dispatcher fast-path.  The inline copy below is the
    import-failure last resort only — tests/unit/test_fallback_parity.py pins
    it against the shared table on a fixed corpus.
    """
    try:
        from fallback_keywords import classify  # plugin src/ (slice-rewritten)
        return classify(prompt)
    except ImportError:
        pass
    import re
    p = prompt.lower()
    # Precedence contract (must mirror fallback_keywords.BRANCH_ORDER):
    # A → B → C → D → E, first match wins; bias-to-D for implement verbs;
    # short words use word boundaries ('new' in 'renew' must not match).
    if any(k in p for k in ["broken", "bug", "error", "fix", "stack trace", "failing", "exception", "traceback", "crash"]):
        return "A"
    elif any(k in p for k in ["design", "architecture", "brainstorm", "spec out", "roadmap"]) or re.search(r"\bplan\b", p):
        return "B"
    elif any(k in p for k in ["explain", "what does", "walk me through", "which file"]) or re.search(r"\b(?:how|where|which)\b", p):
        return "C"
    elif any(k in p for k in ["typo", "change color", "minor update", "rename", "refactor", "add", "create", "write", "build", "set up", "update"]) or re.search(r"\b(?:implement|new)\b", p):
        return "D"
    else:
        return "E"

def _search_first_pending(branch, plugin_root, session_id):
    """F4 steering predicate: True only on Branch B when the search-first
    toggle is on and research_done is unset for this session.  Branch-scoped
    so every non-B prompt skips the session-store I/O (hot path).  Fail-open:
    any error reads as not-pending — the line only steers; enforcement lives
    in pre_tool_use keyed to the persisted phase (R2)."""
    if branch != "B":
        return False
    try:
        from hook_common import feature_enabled, get_research_done
        if not feature_enabled("pipeline.dispatcher.gates.search_first", plugin_root):
            return False
        return not get_research_done(plugin_root, session_id)
    except Exception:
        return False


def _load_business(branch):
    """Load the compiled business digest from domain.json — but only on the
    branches where build_context will inject it (UserPromptSubmit is a hot
    path; every other prompt skips the manifest I/O). Best-effort; never
    breaks the hook."""
    try:
        from context_builder import _BUSINESS_BRANCHES
    except Exception:
        _BUSINESS_BRANCHES = ("B", "C")
    if branch not in _BUSINESS_BRANCHES:
        return {}
    try:
        from model import OpsManifest  # deployed flat in the plugin
        _dj = os.environ.get("DOMAIN_JSON_PATH")
        if _dj:
            _djp = Path(_dj)
        else:
            try:
                from hook_common import resolve_plugin_root
                _djp = resolve_plugin_root() / "domain" / "domain.json"
            except Exception:
                _djp = Path.cwd() / "domain.json"
        if _djp.exists():
            return OpsManifest.load(_djp).business
    except Exception as e:
        print(f"DEBUG: business load failed: {e}", file=sys.stderr)
    return {}

# capture_output=False: main() ends in sys.exit(0) (returns None); the default
# auto-capture would overwrite the span output we set via complete_prompt_span.
@observe(name="user_prompt", capture_output=False)
def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("Error: Malformed JSON from agent.", file=sys.stderr)
            sys.exit(2)
            
        prompt = input_data.get("prompt", "")
        project_root = resolve_project_root(input_data)
        branch = None
        reason = None
        routing_decision = {}
        dispatcher = None
        
        # 1. Setup paths to import OrchestratorDispatcher
        current_dir = Path(__file__).parent
        plugin_root = current_dir.parent
        src_dir = plugin_root / "src"
        # Config JSONs (agents.json, rules.json, orchestrator.json) are minted to
        # the plugin root, not a config/ subdir — see plugin_generator.py.
        config_dir = plugin_root
        
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        import langfuse_instrumentation
        langfuse_instrumentation.init_langfuse_trace(str(project_root))
        langfuse_instrumentation.init_langfuse_prompt_span(prompt)

        try:
            from dispatcher import OrchestratorDispatcher

            # 3. Instantiate dispatcher
            dispatcher = OrchestratorDispatcher(str(config_dir))
            
            # 4. Dispatch agent to get intent
            result = dispatcher.dispatch_agent("orchestrator", {
                "prompt": prompt,
                "project_root": str(project_root)
            })
            
            branch = result.get("intent_branch")
            reason = result.get("intent_justification")
            routing_decision = result.get("routing_decision", {})
            
        except Exception as e:
            print(f"DEBUG: Dispatcher failed: {e}", file=sys.stderr)
            pass
            
        # 5. Fallback if dispatcher failed
        if not branch:
            branch = fallback_classify(prompt)
            reason = "Fallback keyword match"
            
            try:
                # Attempt to get routing decision directly if dispatcher instantiation works but dispatch failed
                dispatcher = OrchestratorDispatcher(str(config_dir))
                routing_decision = dispatcher.evaluate_artifacts(branch, project_root)
            except Exception:
                pass

        # Apply Plan A–E branch toggles: a disabled branch degrades to E
        # (answer-only). Recompute routing on the effective branch so the
        # SYSTEM STATE (phase/auth/agent) reflects the branch that runs.
        try:
            from hook_common import effective_branch
            _eff = effective_branch(branch, plugin_root)
            if _eff != branch:
                branch = _eff
                try:
                    if dispatcher is None:
                        dispatcher = OrchestratorDispatcher(str(config_dir))
                    routing_decision = dispatcher.evaluate_artifacts(branch, project_root)
                except Exception:
                    routing_decision = {}
        except Exception:
            pass

        current_phase = routing_decision.get("phase", "Unknown")
        auth_msg = routing_decision.get("auth_msg", "")
        target_agent = routing_decision.get("target_agent", "@generalist")
        # Apply agents.* toggles: a disabled persona degrades to @generalist.
        try:
            from hook_common import effective_agent
            target_agent = effective_agent(target_agent, plugin_root)
        except Exception:
            pass
        manifest_state = routing_decision.get("manifest_state", None)

        # Phase 6a: resolve identity ONCE from the hook payload (platform
        # truth), publish the pointer so skill-invoked scripts share this
        # store, and use one state root for every session/feature read
        # (review #7: no dual resolution paths).
        try:
            from hook_common import get_session_id, publish_session_pointer
            state_root = resolve_plugin_root()
            session_id = get_session_id(input_data)
            publish_session_pointer(state_root, session_id)
        except Exception:
            state_root = plugin_root
            session_id = None

        try:
            if session_id is None:
                # Identity resolution failed (fail-open above) — skip the
                # campaign-state write rather than keying a "null" session.
                raise RuntimeError("no session id")
            state_dir = state_root / "state"
            state_dir.mkdir(exist_ok=True)
            state_file = state_dir / "campaign_state.json"

            state_data = {}
            if state_file.exists():
                try:
                    with open(state_file, "r") as f:
                        state_data = json.load(f)
                except json.JSONDecodeError:
                    pass

            if "sessions" not in state_data:
                state_data["sessions"] = {}
                
            if session_id not in state_data["sessions"]:
                state_data["sessions"][session_id] = {}
                
            if target_agent:
                active_persona = target_agent.lstrip("@")
                state_data["sessions"][session_id]["active_persona"] = active_persona
                state_data["active_persona"] = active_persona
            
            with open(state_file, "w") as f:
                json.dump(state_data, f, indent=2)
        except Exception as e:
            print(f"DEBUG: Failed to save campaign state: {e}", file=sys.stderr)

        # Load the compiled business digest (small) so build_context can push it
        # on planning/question branches. Skips the I/O on every other branch.
        business = _load_business(branch)

        # F4 steering: gate-status flag for Branch B (skips I/O on other branches).
        try:
            sf_pending = (
                _search_first_pending(branch, state_root, session_id)
                if session_id else False
            )
        except Exception:
            sf_pending = False

        try:
            from context_builder import build_context
            system_state = build_context(
                phase=current_phase,
                target_agent=target_agent,
                auth_msg=auth_msg,
                branch=branch,
                manifest_state=manifest_state,
                business=business,
                search_first_pending=sf_pending,
                session_id=session_id
            )
        except Exception as e:
            print(f"DEBUG: context_builder failed: {e}", file=sys.stderr)
            system_state = ""
            if current_phase != "Unknown":
                system_state = f"\n\n=== SYSTEM STATE ===\nActive Branch: {branch}\nCurrent Phase: {current_phase}\nTarget Agent: {target_agent}\nAuthorization: {auth_msg}\n"
                if session_id:
                    system_state += f"Session: {session_id}\n"
                if manifest_state and branch == "B":
                    system_state += f"Proposed Designs: {', '.join(manifest_state.get('designs_found', [])) or 'None'}\n"
                    system_state += f"In-Progress Designs: {', '.join(manifest_state.get('progress_found', [])) or 'None'}\n"
                if sf_pending and branch == "B":
                    system_state += (
                        "Search-First Gate: research_done NOT set — run the search-first skill "
                        "(or record its proportionality waiver) before source edits.\n"
                    )
                system_state += "====================\n"

        # Append staleness warning when features.yaml is out-of-sync (fail-open).
        try:
            from hook_common import features_staleness_warning
            _stale_warn = features_staleness_warning(state_root)
            if _stale_warn:
                system_state = (system_state.rstrip() + "\n" + _stale_warn + "\n") if system_state else (_stale_warn + "\n")
        except Exception:
            pass
            
        hook_event_name = input_data.get("hookEventName") or input_data.get("hook_event_name", "UserPromptSubmit")
        
        routing_decision["classification"] = branch
        routing_decision["reason"] = reason

        try:
            from platform_adapter import get_adapter
            adapter = get_adapter()
            output = adapter.format_hook_response(
                original_prompt=prompt,
                routing_decision=routing_decision,
                context_extension=system_state,
                hook_event_name=hook_event_name
            )
        except Exception as e:
            print(f"DEBUG: Adapter formatting failed: {e}", file=sys.stderr)
            # Honest, universally-valid degraded response: inject the system
            # state via the one field every platform honours (additionalContext)
            # and let the prompt proceed. We deliberately do NOT emit the
            # invented routing fields (modifiedPrompt/target_agent/...) — codex
            # rejects unknown fields (deny_unknown_fields) and cursor/gemini
            # ignore them, so on the crash path they'd only do harm.
            output = {
                "continue": True,
                "hookSpecificOutput": {
                    "hookEventName": hook_event_name,
                    "additionalContext": system_state,
                },
            }

        langfuse_instrumentation.complete_prompt_span(
            modified_prompt=output.get("modifiedPrompt", prompt),
            system_state=system_state,
            routing_decision=routing_decision,
        )
        print(json.dumps(output))
        langfuse_instrumentation.ensure_flush()
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in prompt_classifier: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()