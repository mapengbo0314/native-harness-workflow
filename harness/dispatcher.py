"""Orchestrator dispatcher for routing agent requests."""
import json
import os
import time
import re
from pathlib import Path
from typing import Any, Dict, Optional


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
        self.state_file = self.config_dir / ".harness_state.json"
        self.tmp_state_file = self.config_dir / ".harness_state.tmp.json"
        self.lock_dir = self.config_dir / ".harness_state.json.lock"

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
        agents_dir = self.config_dir.parent / "agents"
        agents = {}
        if agents_dir.exists():
            for agent_file in agents_dir.glob("*.md"):
                agents[agent_file.stem] = {
                    "path": str(agent_file),
                    "source": agent_file.read_text()[:200]
                }
        return {"agents": agents}

    def _load_rules_config(self) -> Dict[str, Any]:
        """Load rules configuration."""
        config_file = self.config_dir / "rules.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
        return {"rules": {}}

    def _load_state(self) -> Dict[str, Any]:
        """Load state from .harness_state.json."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError, PermissionError):
                pass
        return {"active_persona": "orchestrator", "tdd_status": "inactive"}

    def _save_state(self, state: Dict[str, Any], timeout: float = 5.0) -> None:
        """Save state to .harness_state.json atomically using a directory lock."""
        import os
        import time
        import shutil

        if self.lock_dir.exists():
            try:
                if time.time() - os.path.getmtime(self.lock_dir) > 10.0:
                    try:
                        self.lock_dir.rmdir()
                    except OSError:
                        shutil.rmtree(self.lock_dir, ignore_errors=True)
            except OSError:
                pass

        start_time = time.time()
        while True:
            try:
                # Try to acquire lock
                self.lock_dir.mkdir()
                break
            except FileExistsError:
                if time.time() - start_time > timeout:
                    raise OSError("Could not acquire lock for state file")
                time.sleep(0.05)

        try:
            # Write to temporary file
            with open(self.tmp_state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            # Atomic swap
            os.replace(self.tmp_state_file, self.state_file)
        finally:
            # Release lock
            try:
                self.lock_dir.rmdir()
            except OSError:
                pass

    def classify_intent(self, prompt: str) -> str:
        """Classify user intent into Matrix Routing Branches A/B/C/D.

        Branch A: Bug Fix (stack trace, error, broken)
        Branch B: Feature Request (build, create, implement)
        Branch C: Question (how does, where is)
        Branch D: Surgical Edit (typo, change color)
        """
        prompt_lower = prompt.lower()
        
        # Branch A: Bug Fix / Diagnosis
        if any(keyword in prompt_lower for keyword in ["traceback", "stack trace", "error", "broken", "bug"]):
            return "A"
            
        # Branch C: Question (Check before B as "How do I implement" is a question)
        if any(keyword in prompt_lower for keyword in ["how does", "where is", "what is", "explain"]):
            return "C"
            
        # Branch B: Feature Request & Architectural Planning
        if any(keyword in prompt_lower for keyword in ["implement", "build", "create", "add feature", "new"]):
            return "B"
            
        # Branch D: Surgical Edit (Fast Path)
        if any(keyword in prompt_lower for keyword in ["typo", "change color", "minor update", "fix the"]):
            return "D"
            
        # Default to B if we can't classify
        return "B"

    def validate_verb(self, verb: str) -> bool:
        """Validate if the intent starts with a valid 5-Verb."""
        return verb in self.VALID_VERBS

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
        # Validate agent exists in config
        agents = self.agents_config.get("agents", {})
        if agent_name not in agents:
            raise ValueError(f"Agent '{agent_name}' not found in configuration")

        # Apply orchestrator rules
        if not self.validate_against_rules(agent_name):
            raise PermissionError(f"Agent '{agent_name}' violates project rules")

        # Basic intent classification if prompt is provided
        intent_branch = None
        if "prompt" in context:
            intent_branch = self.classify_intent(context["prompt"])

        # Update state
        state = self._load_state()
        state["active_persona"] = agent_name
        if agent_name == "implementer":
            state["tdd_status"] = "active"
        self._save_state(state)

        return {
            "agent": agent_name,
            "routed": True,
            "context": context,
            "orchestrator_applied": True,
            "intent_branch": intent_branch,
            "state": state
        }

    def validate_against_rules(self, agent_name: str) -> bool:
        """Validate agent request against project rules.

        Args:
            agent_name: Name of the agent

        Returns:
            True if valid
        """
        # For now, always valid - could be extended to parse rules
        return True
