"""Orchestrator dispatcher for routing agent requests."""
import json
import os
import time
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
from dotenv import load_dotenv
from langfuse.decorators import observe, langfuse_context
import uuid

load_dotenv()

try:
    from harness.runtime.llm_client import query_llm
except (ImportError, ValueError):
    try:
        from .llm_client import query_llm
    except (ImportError, ValueError):
        query_llm = None


class OrchestratorDispatcher:
    """Routes agent requests through the project's orchestrator."""

    VALID_VERBS = {"/plan", "/work", "/review", "/release", "/setup"}

    def __init__(self, config_dir: str):
        """Initialize dispatcher with plugin config.

        Args:
            config_dir: Path to .claude/plugin-generated/config
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

    @observe(as_type="span")
    def classify_intent(self, prompt: str) -> Dict[str, str]:
        """Classify user intent into Matrix Routing Branches A/B/C/D.

        Returns:
            Dict with 'branch' and 'justification'
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        cli_name = None
        if not api_key:
            cli_name = os.environ.get("HARNESS_PLATFORM_CLI")
            if not cli_name:
                if shutil.which("claude"):
                    cli_name = "claude"
                elif shutil.which("gemini"):
                    cli_name = "gemini"

        if query_llm and (api_key or cli_name):
            classification_prompt = f"""
Analyze the following user prompt and classify it into one of the following Matrix Routing Branches:

- Branch A: Bug Fix / Diagnosis (e.g., stack trace, error, broken, bug)
- Branch B: Feature Request & Architectural Planning (e.g., build, create, implement, add feature, new)
- Branch C: Codebase Questioning & Knowledge Retrieval (e.g., how does, where is, what is, explain)
- Branch D: Surgical Edit / Fast Path (e.g., typo, change color, minor update, fix the)

User Prompt: "{prompt}"

Before choosing the branch, provide a brief justification (Chain of Thought).
Return the result as JSON:
{{
  "intent_analysis": "Your justification here",
  "selected_branch": "Branch A, B, C, D, or E"
}}
"""
            try:
                if api_key:
                    # Use gemini-2.5-flash-lite as requested in mandate
                    model = os.environ.get("HARNESS_MODEL", "gemini-2.5-flash-lite")
                    response = query_llm(classification_prompt, "gemini", api_key, model=model)
                else:
                    response = query_llm(classification_prompt, "native_cli", api_key=cli_name)
                
                # Extract JSON
                cleaned = response.replace("```json", "").replace("```", "").strip()
                start_idx = cleaned.find("{")
                end_idx = cleaned.rfind("}") + 1
                if start_idx != -1 and end_idx != 0:
                    cleaned = cleaned[start_idx:end_idx]
                
                data = json.loads(cleaned)
                branch_str = data.get("selected_branch", "Branch B")
                # Normalize branch string (e.g., "Branch A" -> "A")
                branch = branch_str.replace("Branch ", "").split(":")[0].strip()
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
        pointers.append("Available Skills Index: .gemini/skills_index.json")
        pointers.append("To load a skill, run: python3 scripts/activate_skill.py <skill_name>")
        
        if intent_branch == "A":
            pointers.append("Branch A (Bug Fix): Focus on stack traces and isolate the error. Use mcp_codegraph_codegraph_callers.")
        elif intent_branch == "B":
            pointers.append("Branch B (Feature/Arch): Focus on step-by-step planning. Use harness-brainstorming-plans and harness-brainstorming-plans.")
        elif intent_branch == "C":
            pointers.append("Branch C (Question): Do not modify files. Use codegraph to explore.")
        elif intent_branch == "D":
            pointers.append("Branch D (Surgical Edit): Bypass heavy planning. Use implementer directly.")
            
        return "\n".join(pointers)

    @observe()
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

        # Validate agent exists in config
        agents = self.agents_config.get("agents", {})
        if agent_name != "orchestrator" and agent_name not in agents:
            raise ValueError(f"Agent '{agent_name}' not found in configuration")

        # Basic intent classification if prompt is provided
        intent_branch = None
        intent_justification = None
        if "prompt" in context:
            intent_info = self.classify_intent(context["prompt"])
            intent_branch = intent_info.get("branch")
            intent_justification = intent_info.get("justification")
            
            # Surface reasoning to the top-level trace
            langfuse_context.update_current_trace(
                metadata={
                    "matrix_branch": intent_branch,
                    "intent_justification": intent_justification
                }
            )

        branch_pointers = self.assemble_branch_context(agent_name, str(intent_branch) if intent_branch else "None")
        context["branch_context_pointers"] = branch_pointers

        return {
            "agent": agent_name,
            "routed": True,
            "context": context,
            "orchestrator_applied": True,
            "intent_branch": intent_branch,
            "intent_justification": intent_justification,
            "trace_id": langfuse_context.get_current_trace_id()
        }
