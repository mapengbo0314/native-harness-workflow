"""Orchestrator dispatcher for routing agent requests."""
import json
from pathlib import Path
from typing import Any, Dict, Optional


class OrchestratorDispatcher:
    """Routes agent requests through the project's orchestrator."""

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
        return {"agents": {}}

    def _load_rules_config(self) -> Dict[str, Any]:
        """Load rules configuration."""
        config_file = self.config_dir / "rules.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
        return {"rules": {}}

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

        return {
            "agent": agent_name,
            "routed": True,
            "context": context,
            "orchestrator_applied": True
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
