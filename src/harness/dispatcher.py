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
    from harness.database import HarnessDB
except (ImportError, ValueError):
    try:
        from .database import HarnessDB
    except (ImportError, ValueError):
        try:
            import database
            HarnessDB = database.HarnessDB
        except ImportError:
            # Fallback for environments where database.py might not be available yet
            HarnessDB = None

try:
    from harness.discovery_engine import query_llm
except (ImportError, ValueError):
    try:
        from .discovery_engine import query_llm
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
        self.state_file = self.config_dir / ".harness_state.json"
        self.tmp_state_file = self.config_dir / ".harness_state.tmp.json"
        self.db = HarnessDB(str(self.config_dir / "harness.db"))

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

    def _load_state(self) -> Dict[str, Any]:
        """Load state from HarnessDB with fallback to .harness_state.json."""
        # Try DB first
        db_state = self.db.get_state()
        if db_state:
            return db_state

        # Fallback to file for migration
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    # Migrate to DB
                    self.db.set_state(state)
                    return state
            except (json.JSONDecodeError, OSError, PermissionError):
                pass
        return {
            "active_persona": "orchestrator",
            "tdd_status": "inactive",
            "matrix_branch": None,
            "consecutive_rejections": 0,
            "setup_complete": False,
            "strict_enforcement_enabled": False,
        }

    def _save_state(self, state: Dict[str, Any], timeout: float = 5.0) -> None:
        """Save state to HarnessDB and .harness_state.json atomically using SQLite leases."""
        start_time = time.time()
        locked = False
        while time.time() - start_time < timeout:
            if self.db.acquire_lease("state_lock", ttl_seconds=10):
                locked = True
                break
            time.sleep(0.05)

        if not locked:
            raise OSError("Could not acquire lock for state file")

        try:
            # Save to DB
            self.db.set_state(state)

            # Also save to file for backward compatibility
            with open(self.tmp_state_file, 'w') as f:
                json.dump(state, f, indent=2)
            os.replace(self.tmp_state_file, self.state_file)
        finally:
            # Release lock
            self.db.release_lease("state_lock")

    @observe(as_type="span")
    def classify_intent(self, prompt: str) -> Dict[str, str]:
        """Classify user intent into Matrix Routing Branches A/B/C/D.

        Returns:
            Dict with 'branch' and 'justification'
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if query_llm and api_key:
            classification_prompt = f"""
Analyze the following user prompt and classify it into one of the following Matrix Routing Branches:

- Branch A: Bug Fix / Diagnosis (e.g., stack trace, error, broken, bug)
- Branch B: Feature Request & Architectural Planning (e.g., build, create, implement, add feature, new)
- Branch C: Codebase Questioning & Knowledge Retrieval (e.g., how does, where is, what is, explain)
- Branch D: Surgical Edit / Fast Path (e.g., typo, change color, minor update, fix the)
- Branch E: Verification Remediation (e.g., verification failed, tests failing, QA report issues)

User Prompt: "{prompt}"

Before choosing the branch, provide a brief justification (Chain of Thought).
Return the result as JSON:
{{
  "intent_analysis": "Your justification here",
  "selected_branch": "Branch A, B, C, D, or E"
}}
"""
            try:
                # Use gemini-2.5-flash-lite as requested in mandate
                model = os.environ.get("HARNESS_MODEL", "gemini-2.5-flash-lite")
                response = query_llm(classification_prompt, "gemini", api_key, model=model)
                
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

        # Update state and check for infinite loops
        state = self._load_state()
        
        # Infinite loop prevention (individual tracking)
        counts = state.get("agent_cycle_counts", {})
        if not isinstance(counts, dict):
            counts = {}

        if agent_name in ["implementer", "reviewer", "verifier"]:
            current_count = counts.get(agent_name, 0) + 1
            if current_count > 4:
                # Reset the counter for this agent so it's not permanently stuck, but block this dispatch
                counts[agent_name] = 0
                state["agent_cycle_counts"] = counts
                self._save_state(state)
                raise PermissionError(
                    f"INFINITE LOOP DETECTED: The {agent_name} has been dispatched 5 times without breaking the cycle. "
                    "You MUST STOP dispatching subagents immediately. "
                    "Use the `ask_user` tool or `ask` tool to notify the user of the unresolved issues "
                    "and wait for human intervention."
                )
            counts[agent_name] = current_count
            state["agent_cycle_counts"] = counts
        else:
            # If we dispatch a planner or other agent, reset all execution cycle counts
            state["agent_cycle_counts"] = {}

        # Apply orchestrator rules (like Gatekeeper)
        if not self.validate_against_rules(agent_name):
            raise PermissionError(f"Agent '{agent_name}' violates project rules")

        state["active_persona"] = agent_name
        state["matrix_branch"] = intent_branch
        state["intent_justification"] = intent_justification
        if agent_name == "implementer":
            state["tdd_status"] = "active"
        self._save_state(state)

        return {
            "agent": agent_name,
            "routed": True,
            "context": context,
            "orchestrator_applied": True,
            "intent_branch": intent_branch,
            "intent_justification": intent_justification,
            "state": state,
            "trace_id": langfuse_context.get_current_trace_id()
        }

    def validate_against_rules(self, agent_name: str) -> bool:
        """Validate agent request against project rules.

        Args:
            agent_name: Name of the agent

        Returns:
            True if valid
        """
        if agent_name == "implementer":
            try:
                gatekeeper = self.config_dir.parent / "scripts" / "gatekeeper.py"
                workspace = self.config_dir.parent.parent.parent
                if gatekeeper.exists():
                    result = subprocess.run(
                        [sys.executable, str(gatekeeper), "--phase", "3", "--workspace", str(workspace)],
                        capture_output=True,
                        text=True,
                        env=os.environ.copy()
                    )
                    if result.returncode != 0:
                        error_msg = result.stderr or result.stdout
                        raise PermissionError(f"Gatekeeper Phase 3 failed: {error_msg}. Dispatch @planner first to create the implementation plan.")
            except Exception as e:
                if isinstance(e, PermissionError):
                    raise
                # Ignore if gatekeeper is missing or other errors occur during check
                pass
                
        return True
