import sys
import json
import os
import logging
from pathlib import Path
from hook_common import resolve_project_root
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
    prompt = prompt.lower()
    if any(k in prompt for k in ["broken", "bug", "error", "fix", "stack trace"]):
        return "A"
    elif any(k in prompt for k in ["build", "implement", "design", "architecture", "plan", "feature"]):
        return "B"
    elif any(k in prompt for k in ["how", "where", "explain"]):
        return "C"
    elif any(k in prompt for k in ["typo", "change color", "minor update", "fix the", "rename"]):
        return "D"
    else:
        return "E"

@observe(name="user_prompt")
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
        config_dir = plugin_root / "config"
        
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        import langfuse_instrumentation
        langfuse_instrumentation.init_langfuse_trace(str(project_root))
        langfuse_instrumentation.init_langfuse_prompt_span(prompt)

        try:
            from harness.runtime.dispatcher import OrchestratorDispatcher
            
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

        current_phase = routing_decision.get("phase", "Unknown")
        artifacts_missing = routing_decision.get("artifacts_missing", [])
        auth_msg = routing_decision.get("auth_msg", "")
        target_agent = routing_decision.get("target_agent", "@generalist")
        manifest_state = routing_decision.get("manifest_state", None)

        try:
            from hook_common import resolve_plugin_root, get_session_id
            state_dir = resolve_plugin_root() / "state"
            state_dir.mkdir(exist_ok=True)
            state_file = state_dir / "campaign_state.json"
            
            state_data = {}
            if state_file.exists():
                try:
                    with open(state_file, "r") as f:
                        state_data = json.load(f)
                except json.JSONDecodeError:
                    pass
                    
            session_id = get_session_id()
            
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

        try:
            from harness.runtime.context_builder import build_context
            system_state = build_context(
                phase=current_phase,
                target_agent=target_agent,
                auth_msg=auth_msg,
                branch=branch,
                missing_documents=artifacts_missing,
                manifest_state=manifest_state
            )
        except Exception as e:
            print(f"DEBUG: context_builder failed: {e}", file=sys.stderr)
            system_state = ""
            if current_phase != "Unknown":
                system_state = f"\n\n=== SYSTEM STATE ===\nActive Branch: {branch}\nCurrent Phase: {current_phase}\nTarget Agent: {target_agent}\nArtifacts Missing: {', '.join(artifacts_missing) if artifacts_missing else 'None'}\nAuthorization: {auth_msg}\n"
                if manifest_state and branch == "B":
                    system_state += f"Proposed Designs: {', '.join(manifest_state.get('designs_found', [])) or 'None'}\n"
                    system_state += f"In-Progress Designs: {', '.join(manifest_state.get('progress_found', [])) or 'None'}\n"
                system_state += "====================\n"
            
        hook_event_name = input_data.get("hookEventName") or input_data.get("hook_event_name", "UserPromptSubmit")
        
        routing_decision["classification"] = branch
        routing_decision["reason"] = reason

        try:
            from harness.adapters import get_adapter
            platform_id = os.environ.get("HARNESS_PLATFORM_CLI", "generic")
            adapter = get_adapter(platform_id)
            output = adapter.format_hook_response(
                original_prompt=prompt,
                routing_decision=routing_decision,
                context_extension=system_state,
                hook_event_name=hook_event_name
            )
        except Exception as e:
            print(f"DEBUG: Adapter formatting failed: {e}", file=sys.stderr)
            output = {
                "classification": branch, 
                "modifiedPrompt": prompt + system_state,
                "system_prompt_extension": system_state,
                "target_agent": target_agent,
                "hookSpecificOutput": {
                    "hookEventName": hook_event_name,
                    "systemPromptExtension": system_state,
                    "modifiedPrompt": prompt + system_state,
                    "target_agent": target_agent
                }
            }
            
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