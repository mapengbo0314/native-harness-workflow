"""Orchestrator dispatcher for routing agent requests."""
import json
import os
import shutil
import time
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
from dotenv import load_dotenv
from langfuse import observe
from harness.runtime.langfuse_compat import langfuse_context
import uuid

load_dotenv()


def get_active_platform_and_model(starting_dir: str = ".") -> Tuple[str, str]:
    """Detect active platform and determine the model being used.

    Checks HARNESS_PLATFORM_CLI env var first (set by hooks from their own path),
    then falls back to traversing up the directory tree for platform directories.
    Checks HARNESS_MODEL environment variable for custom model overrides.

    Args:
        starting_dir: Directory to start traversal from. Defaults to current directory.

    Returns:
        Tuple of (platform_name, model_name). Examples:
          (".claude", "claude-haiku-4.5")
          (".gemini", "gemini-2.5-flash-lite")
          (".codex", "gpt-4")
          (".cursor", "claude")
          ("unknown", "unknown-model")
    """
    _PLATFORM_DEFAULTS = {
        ".claude": "claude-haiku-4.5",
        ".gemini": "gemini-2.5-flash-lite",
        ".codex": "gpt-4",
        ".cursor": "claude",
    }

    # Prefer env var set by the hook — avoids ambiguity when multiple platform
    # dirs coexist in the same repo (e.g. both .claude/ and .gemini/).
    cli_platform = os.environ.get("HARNESS_PLATFORM_CLI", "").lower()
    if cli_platform in ("claude", "gemini", "codex", "cursor"):
        platform = f".{cli_platform}"
        model = os.environ.get("HARNESS_MODEL") or _PLATFORM_DEFAULTS.get(platform, "unknown-model")
        return (platform, model)

    # Fallback: traverse up looking for platform directory
    current = Path(starting_dir).resolve()
    platform = None
    while current != current.parent:
        for name in (".claude", ".gemini", ".codex", ".cursor"):
            if (current / name).exists():
                platform = name
                break
        if platform:
            break
        current = current.parent

    model = os.environ.get("HARNESS_MODEL") or _PLATFORM_DEFAULTS.get(platform or "", "")
    if not model:
        model = f"{cli_platform}-unknown" if cli_platform else "unknown-model"

    return (platform or "unknown", model)

try:
    import harness.runtime.llm_client as _llm_client_module
    from harness.runtime.llm_client import query_llm
except (ImportError, ValueError):
    try:
        from . import llm_client as _llm_client_module
        from .llm_client import query_llm
    except (ImportError, ValueError):
        _llm_client_module = None
        query_llm = None


class OrchestratorDispatcher:
    """Routes agent requests through the project's orchestrator."""

    VALID_VERBS = {"/plan", "/work", "/review", "/release", "/setup"}

    BRANCHES = {
        "A": "Bug Fix / Diagnosis (stack trace, error, broken, bug, why is X failing)",
        "B": "Feature Request & Architectural Planning (build, create, implement, add feature, new)",
        "C": "Codebase Questioning & Knowledge Retrieval (how does, where is, what is, explain, why does)",
        "D": "Code Edit / TDD Required (any code change: rename, refactor, new function, fix, update)",
        "E": "No Technical Intent (conversational, greetings, vague messages with zero actionable intent)",
    }

    BRANCH_ROUTING = {
        "A": {"skill": "harness-systematic-debugging",    "agent": "debugger",     "agent_invokes_skill": True},
        "B": {"skill": "harness-brainstorming-plans",     "agent": "planner",      "agent_invokes_skill": False},
        "C": {"skill": None,                              "agent": "generalist",   "agent_invokes_skill": False},
        "D": {"skill": "harness-test-driven-development", "agent": "implementer",  "agent_invokes_skill": True},
        "E": {"skill": None,                              "agent": None,           "agent_invokes_skill": False},
    }

    def __init__(self, config_dir: str):
        """Initialize dispatcher with plugin config.

        Args:
            config_dir: Path to .claude/harness-wf-plugin/config
        """
        self.config_dir = Path(config_dir)
        self.orchestrator_config = self._load_orchestrator_config()
        self.agents_config = self._load_agents_config()
        self.rules_config = self._load_rules_config()

    def _load_orchestrator_config(self) -> Dict[str, Any]:
        """Load orchestrator configuration."""
        config_file = self.config_dir / "orchestrator.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
        return {}

    def _load_agents_config(self) -> Dict[str, Any]:
        """Load agents configuration."""
        config_file = self.config_dir / "agents.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
                
        # Fallback for deep copy migration
        agents_dir = self.config_dir / "agents"
        agents = {}
        if agents_dir.exists():
            for agent_file in agents_dir.glob("*.md"):
                agents[agent_file.stem] = {
                    "path": str(agent_file),
                    "source": agent_file.read_text()
                }
        return {"agents": agents}

    def _load_rules_config(self) -> Dict[str, Any]:
        """Load rules configuration."""
        config_file = self.config_dir / "rules.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
        return {"rules": {}}

    @observe(name="classify_intent", as_type="span")
    def classify_intent(self, prompt: str) -> Dict[str, str]:
        """Classify user intent into Matrix Routing Branches A/B/C/D.

        Returns:
            Dict with 'branch' and 'justification'
        """
        cli_name = os.environ.get("HARNESS_PLATFORM_CLI")
        if not cli_name:
            if shutil.which("claude"):
                cli_name = "claude"
            elif shutil.which("gemini"):
                cli_name = "gemini"

        if query_llm and cli_name:
            branch_menu = "\n".join(f"  {k} - {v}" for k, v in self.BRANCHES.items())
            valid_keys = list(self.BRANCHES.keys())
            classification_prompt = f"""
Classify the following user prompt into exactly one routing branch.

Choose a single letter from this list:
{branch_menu}

User Prompt: "{prompt}"

Return ONLY valid JSON — no markdown, no extra text:
{{
  "intent_analysis": "one-sentence justification",
  "selected_branch": "X"
}}

selected_branch MUST be exactly one of: {valid_keys}
"""
            try:
                response = query_llm(classification_prompt, cli_name)
                # Prefer actual model from CLI response, fall back to platform detection
                actual_model = getattr(_llm_client_module, "last_actual_model", None)
                if not actual_model:
                    _, actual_model = get_active_platform_and_model()
                langfuse_context.update_current_observation(model=actual_model)

                # Extract JSON
                cleaned = response.replace("```json", "").replace("```", "").strip()
                start_idx = cleaned.find("{")
                end_idx = cleaned.rfind("}") + 1
                if start_idx != -1 and end_idx != 0:
                    cleaned = cleaned[start_idx:end_idx]

                data = json.loads(cleaned)
                branch = data.get("selected_branch", "E").strip().upper()
                if branch not in self.BRANCHES:
                    branch = "E"
                return {
                    "branch": branch,
                    "justification": data.get("intent_analysis", "No justification provided.")
                }
            except Exception as e:
                # Fallback to keyword matching if LLM fails
                print(f"DEBUG: LLM intent classification failed: {e}")
                pass

        prompt_lower = prompt.lower()
        
        # Branch A: Bug Fix / Diagnosis
        if any(keyword in prompt_lower for keyword in ["traceback", "stack trace", "error", "broken", "bug"]):
            return {"branch": "A", "justification": "Keyword match: detected error-related keywords."}
            
        # Branch C: Question (Check before B as "How do I implement" is a question)
        if any(keyword in prompt_lower for keyword in ["how does", "where is", "what is", "explain"]):
            return {"branch": "C", "justification": "Keyword match: detected questioning keywords."}
            
        # Branch B: Feature Request & Architectural Planning
        if any(keyword in prompt_lower for keyword in ["implement", "build", "create", "add feature", "new"]):
            return {"branch": "B", "justification": "Keyword match: detected feature-creation keywords."}
            
        # Branch D: Surgical Edit (Fast Path)
        if any(keyword in prompt_lower for keyword in ["typo", "change color", "minor update", "fix the"]):
            return {"branch": "D", "justification": "Keyword match: detected surgical edit keywords."}
            
        # Default to B if we can't classify
        return {"branch": "B", "justification": "Default branch: could not reliably classify intent."}

    def validate_verb(self, verb: str) -> bool:
        """Validate if the intent starts with a valid 5-Verb."""
        return verb in self.VALID_VERBS

    def assemble_branch_context(self, agent_name: str, intent_branch: str) -> str:
        """Assemble a branch-specific context pointer string to reduce prompt bloat."""
        pointers = []
        pointers.append(f"Agent Persona: {agent_name}")
        pointers.append(f"Routing Branch: {intent_branch}")
        
        # Add dynamic pointers rather than full text
        platform, _ = get_active_platform_and_model()
        skills_platform = platform if platform != "unknown" else ".claude"
        # skills.json now lives inside the plugin dir (config_dir.parent), not the harness root.
        # For Claude: .claude/harness-wf-plugin/skills.json
        # For other platforms that don't use a plugin, fall back to the harness root.
        from harness.adapters.profile import load_profile as _load_profile
        try:
            _profile = _load_profile(skills_platform.lstrip("."))
            if _profile.supports_plugin:
                skills_pointer = f"{skills_platform}/{_profile.plugin_dir_name}/skills.json"
            else:
                _SKILLS_FILENAMES = {".claude": "skills.json"}
                skills_filename = _SKILLS_FILENAMES.get(skills_platform, "skills_index.json")
                skills_pointer = f"{skills_platform}/{skills_filename}"
        except Exception:
            _SKILLS_FILENAMES = {".claude": "skills.json"}
            skills_filename = _SKILLS_FILENAMES.get(skills_platform, "skills_index.json")
            skills_pointer = f"{skills_platform}/{skills_filename}"
        pointers.append(f"Available Skills Index: {skills_pointer}")
        pointers.append("To load a skill, run: python3 scripts/activate_skill.py <skill_name>")
        
        branch_hints = {
            "A": "Branch A (Bug Fix): Focus on stack traces and isolate the error. Use mcp_codegraph_codegraph_callers.",
            "B": "Branch B (Feature/Arch): Focus on step-by-step planning. Use harness-brainstorming-plans.",
            "C": "Branch C (Question): Do not modify files. Use codegraph to explore.",
            "D": "Branch D (Surgical Edit): Bypass heavy planning. Use generalist directly.",
            "E": "Branch E (No Intent): Respond conversationally. Do not modify files or invoke analysis tools.",
        }
        if intent_branch in branch_hints:
            pointers.append(branch_hints[intent_branch])

        return "\n".join(pointers)

    def evaluate_artifacts(self, branch: str, project_root: Union[str, Path]) -> Dict[str, Any]:
        """Evaluate physical artifacts on disk to deterministically calculate the current Phase.
        Outputs a standardized generic intent dictionary.
        """
        project_root = Path(project_root)
        
        # Robustly resolve harness home by traversing upward from config_dir looking for AGENTS.md
        harness_home = self.config_dir
        while harness_home != harness_home.parent:
            if (harness_home / "AGENTS.md").exists():
                break
            harness_home = harness_home.parent
        
        # Fallback if AGENTS.md is missing for some reason
        if not (harness_home / "AGENTS.md").exists():
            harness_home = self.config_dir.parent.parent
            
        current_phase = "Unknown"
        missing_documents = []
        target_agent = "@generalist"
        auth_msg = ""

        designs_dir = harness_home / "docs" / "designs"
        progress_dir = harness_home / "docs" / "progress"
        
        active_designs = []
        active_progress = []

        if designs_dir.exists():
            for doc in designs_dir.glob("*.md"):
                active_designs.append(doc.name)
                
        if progress_dir.exists():
            for doc in progress_dir.glob("*.md"):
                active_progress.append(doc.name)

        routing = self.BRANCH_ROUTING.get(branch, {"skill": None, "agent": "generalist", "agent_invokes_skill": False})
        target_skill = routing["skill"]
        target_agent = f"@{routing['agent']}" if routing["agent"] else None
        agent_invokes_skill = routing["agent_invokes_skill"]

        phase_map = {
            "A": ("Discovery", "You are UNAUTHORIZED to modify any files. You MUST use read-only tools to diagnose the issue and output the diagnosis report."),
            "B": ("Planning/Execution", "You are authorized to plan or execute based on document state."),
            "C": ("Read-Only", "You are STRICTLY UNAUTHORIZED to mutate any files. You must only read and answer questions."),
            "D": ("TDD Execution", "You are authorized to write code. You MUST follow TDD: write the failing test first."),
            "E": ("Conversational", ""),
        }
        current_phase, auth_msg = phase_map.get(branch, ("Unknown", ""))

        return {
            "phase": current_phase,
            "target_agent": target_agent,
            "target_skill": target_skill,
            "agent_invokes_skill": agent_invokes_skill,
            "missing_documents": missing_documents,
            "auth_msg": auth_msg,
            "manifest_state": {
                "designs_found": active_designs,
                "progress_found": active_progress
            }
        }

    @observe(name="dispatch_agent")
    def dispatch_agent(
        self,
        agent_name: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Route agent request through orchestrator.

        Args:
            agent_name: Name of the agent to dispatch
            context: Agent execution context

        Returns:
            Dispatch result with routed agent info
        """
        # Will be updated with the actual model after classify_intent calls query_llm

        trace_id = os.environ.get("LANGFUSE_TRACE_ID")
        if not trace_id:
            trace_id = str(uuid.uuid4())
            os.environ["LANGFUSE_TRACE_ID"] = trace_id
            
        session_id = os.environ.get("LANGFUSE_SESSION_ID")
        if not session_id:
            session_id = str(uuid.uuid4())
            os.environ["LANGFUSE_SESSION_ID"] = session_id
            
        tags = []
        if os.environ.get("HARNESS_EVAL_MODE") == "1":
            env_tags = os.environ.get("LANGFUSE_TAGS")
            tags = env_tags.split(",") if env_tags else ["integration-test"]
            
        langfuse_context.update_current_trace(session_id=session_id, tags=tags)
        langfuse_context.update_current_observation(
            input={"prompt": context.get("prompt", ""), "agent": agent_name}
        )

        # Validate agent exists in config
        agents = self.agents_config.get("agents", {})
        if agent_name != "orchestrator" and agent_name not in agents:
            raise ValueError(f"Agent '{agent_name}' not found in configuration")

        # Basic intent classification if prompt is provided
        intent_branch = None
        routing_decision = {}
        if "prompt" in context:
            intent_info = self.classify_intent(context["prompt"])
            intent_branch = intent_info.get("branch")

            if intent_branch:
                project_root = context.get("project_root", ".")
                if "project_root" not in context:
                    print("DEBUG: project_root missing from context — routing table used, artifact scan skipped", flush=True)
                routing_decision = self.evaluate_artifacts(intent_branch, project_root)

            # Surface reasoning to the top-level trace
            langfuse_context.update_current_trace(
                metadata={
                    "matrix_branch": intent_branch,
                    "target_agent": routing_decision.get("target_agent"),
                    "phase": routing_decision.get("phase")
                }
            )

        # Always capture the model (actual from last LLM call, or platform-detected fallback)
        actual_model = getattr(_llm_client_module, "last_actual_model", None)
        if not actual_model:
            _, actual_model = get_active_platform_and_model()

        branch_pointers = self.assemble_branch_context(agent_name, str(intent_branch) if intent_branch else "None")
        context["branch_context_pointers"] = branch_pointers

        langfuse_context.update_current_observation(
            model=actual_model,
            output={
                "intent_branch": intent_branch,
                "target_agent": routing_decision.get("target_agent"),
                "phase": routing_decision.get("phase"),
                "routed": True,
            }
        )

        return {
            "agent": agent_name,
            "routed": True,
            "context": context,
            "orchestrator_applied": True,
            "intent_branch": intent_branch,
            "routing_decision": routing_decision,
            "trace_id": langfuse_context.get_current_trace_id()
        }
