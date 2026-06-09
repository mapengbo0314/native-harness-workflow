import os
import json
import subprocess
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import xml.sax.saxutils
import yaml

# Add src and project root to sys.path to import harness and sandbox components
project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

from harness.runtime.dispatcher import OrchestratorDispatcher
from harness.init.discovery_engine import query_llm
from harness.init.minting_engine import mint_workspace
from harness.init.plugin_generator import generate_orchestrator_plugin
from tests.sandbox.scorer import ScenarioScorer


@dataclass
class RoutingResult:
    """The routing decision produced for a scenario.

    Attributes:
        branch: Single-letter routing branch (A/B/C/D/E).
        skill:  Skill invoked by the routed agent, or None if no skill applies.
        agent:  Short agent name (e.g. "implementer"), or None for branch E.
    """

    branch: str
    skill: Optional[str]
    agent: Optional[str]


def run_scenario(plugin_root: Path, scenario: Dict[str, Any]) -> RoutingResult:
    """Run a single routing scenario against the plugin installed at *plugin_root*.

    This is the programmatic entry point for matrix tests.  It exercises only
    the classification + routing-table layer — it does **not** spawn a MockHost,
    call an LLM, or write any files.  The CLI path (``main()``) is unchanged.

    Args:
        plugin_root: Path to the minted plugin directory.  For claude this is
            ``<project>/.claude/harness-wf-plugin/``; for gemini ``<project>/.gemini/``.
        scenario: Scenario dict (same shape as the YAML files under
            ``tests/sandbox/scenarios/``).  Only the ``"prompt"`` key is required.

    Returns:
        A :class:`RoutingResult` with the branch, skill, and agent the plugin
        would route to.
    """
    config_dir = plugin_root / "config"
    dispatcher = OrchestratorDispatcher(str(config_dir))

    prompt = scenario.get("prompt", "")
    intent_info = dispatcher.classify_intent(prompt)
    branch = intent_info.get("branch", "E")

    routing = dispatcher.BRANCH_ROUTING.get(
        branch,
        {"skill": None, "agent": None, "agent_invokes_skill": False},
    )
    skill = routing["skill"]
    agent = routing["agent"]

    return RoutingResult(branch=branch, skill=skill, agent=agent)


def mint_harness(project_path: str, project_name: str, model: str = None):
    """Simplified minting for sandbox runner."""
    project_path = Path(project_path)
    harness_folder = ".claude"
    target_dir = project_path / harness_folder
    
    # Use absolute path for boilerplate to be robust to execution directory
    boilerplate_dir = str(Path(project_root) / "src" / "harness" / "templates" / "boilerplate")
    
    # Mock domain content for SME synthesis
    domain_content = "Proposed Agent Name: @domain-sme\nDomain Invariants:\nNone\n- [x] orchestrator-plugin (local)"
    
    from harness.adapters import get_adapter
    from harness.init.minting_engine import copy_runtime_modules
    # Mint workspace
    mint_workspace(str(target_dir), [], str(project_path), "2", model_choice=model, boilerplate_dir=boilerplate_dir)
    
    copy_runtime_modules(target_dir)
    
    # Generate plugin
    generate_orchestrator_plugin(str(project_path), project_name, boilerplate_dir=boilerplate_dir)

    adapter = get_adapter("claude")
    adapter.generate_core_infrastructure(Path(project_path))

def load_scenario(scenario_path: Path) -> Dict[str, Any]:
    """Loads a scenario from a YAML file."""
    with open(scenario_path, 'r') as f:
        return yaml.safe_load(f)

def setup_scenario_from_data(scenario_data: Dict[str, Any], workspace: Path):
    """Setup a sample project from scenario data."""
    files = scenario_data.get("files", {})
    for file_path, content in files.items():
        full_path = workspace / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

def list_scenarios() -> List[str]:
    """Lists available scenarios (synthetic + captured)."""
    scenarios_dir = Path(project_root) / "tests" / "sandbox" / "scenarios"
    if not scenarios_dir.exists():
        return []
    results = [p.stem for p in scenarios_dir.glob("*.yaml")]
    captured_dir = scenarios_dir / "captured"
    if captured_dir.exists():
        results += [f"captured/{p.stem}" for p in captured_dir.glob("*.yaml")]
    return results

class ToolExecutionEngine:
    """Simulates Claude Code tools in a sandbox environment."""
    
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    def read_file(self, file_path: str = None, start_line: int = None, end_line: int = None, **kwargs) -> str:
        file_path = file_path or kwargs.get('path') or kwargs.get('filename') or kwargs.get('filepath') or kwargs.get('file')
        if not file_path:
            return "Error: Missing required argument 'file_path' (or alias)."
            
        full_path = self.workspace_root / file_path
        if not full_path.exists():
            return f"Error: File {file_path} not found."
        
        with open(full_path, 'r') as f:
            lines = f.readlines()
        
        start = (start_line - 1) if start_line else 0
        end = end_line if end_line else len(lines)
        return "".join(lines[start:end])

    def write_file(self, file_path: str = None, content: str = None, **kwargs) -> str:
        file_path = file_path or kwargs.get('path') or kwargs.get('filename') or kwargs.get('filepath') or kwargs.get('file')
        if not file_path:
            return "Error: Missing required argument 'file_path' (or alias)."
            
        full_path = self.workspace_root / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"

    def replace(self, file_path: str = None, old_string: str = None, new_string: str = None, instruction: str = "", **kwargs) -> str:
        file_path = file_path or kwargs.get('path') or kwargs.get('filename') or kwargs.get('filepath') or kwargs.get('file')
        if not file_path:
            return "Error: Missing required argument 'file_path' (or alias)."
            
        full_path = self.workspace_root / file_path
        if not full_path.exists():
            return f"Error: File {file_path} not found."
        
        with open(full_path, 'r') as f:
            content = f.read()
        
        if old_string not in content:
            return f"Error: Could not find exact match for replacement in {file_path}"
        
        new_content = content.replace(old_string, new_string, 1)
        with open(full_path, 'w') as f:
            f.write(new_content)
        return f"Successfully replaced text in {file_path}"

    def grep_search(self, pattern: str = None, include_pattern: str = None, **kwargs) -> str:
        if not pattern:
            return "Error: Missing required argument 'pattern' for grep_search."
            
        include_pattern = include_pattern or kwargs.get('include')
        
        cmd = ["grep", "-rn", pattern, "."]
        if include_pattern:
            cmd.extend(["--include", include_pattern])
        
        result = subprocess.run(cmd, cwd=self.workspace_root, capture_output=True, text=True)
        return result.stdout if result.stdout else "No matches found."

    def run_shell_command(self, command: str = None) -> Dict[str, Any]:
        if not command:
            return {
                "stdout": "",
                "stderr": "Error: Missing required argument 'command'.",
                "exit_code": 1
            }
            
        result = subprocess.run(
            command,
            shell=True,
            cwd=self.workspace_root,
            capture_output=True,
            text=True
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }

    def glob(self, pattern: str) -> List[str]:
        return [str(p.relative_to(self.workspace_root)) for p in self.workspace_root.glob(pattern)]

    def task(self, agent_name: str, prompt: str, dispatcher: OrchestratorDispatcher) -> str:
        try:
            # This simulates the Task tool in the plugin
            agents = dispatcher.agents_config.get("agents", {})
            if agent_name not in agents:
                return f"Error: Agent '{agent_name}' not found."
            
            agent_data = agents.get(agent_name, {})
            agent_source = agent_data.get("source", "No specific agent instructions found.")
            
            # Simple rule resolution (mocking what's in tools.py)
            rules = dispatcher.rules_config.get("rules", {})
            import re
            def replace_rule(match):
                rule_name = match.group(1).replace('.md', '')
                if rule_name in rules:
                    return f"\n=== MANDATE: {rule_name.upper()} ===\n" + rules[rule_name] + "\n===========================\n"
                return match.group(0)
            
            resolved_source = re.sub(r'@\.\./rules/([a-zA-Z0-9_-]+\.md)', replace_rule, agent_source)
            
            # Update state to reflect active persona
            state = dispatcher._load_state()
            state["active_persona"] = agent_name
            if agent_name == "implementer":
                state["tdd_status"] = "active"
            dispatcher._save_state(state)

            return (
                f"[ORCHESTRATOR APPROVED TASK DISPATCH]\n"
                f"You have been authorized to execute this task as: @{agent_name}\n\n"
                f"=== AGENT PERSONA / INSTRUCTIONS ===\n"
                f"{resolved_source}\n\n"
                f"=== TASK TO EXECUTE ===\n"
                f"{prompt}\n\n"
                f"Please execute the task following the agent persona instructions above."
            )
        except Exception as e:
            return f"Error dispatching task: {str(e)}"

class HarnessEventLogger:
    def __init__(self):
        self.log_file = None
        
    def log_event(self, event_name: str, payload: dict):
        if self.log_file:
            with open(self.log_file, "a") as f:
                f.write(json.dumps({"event": event_name, "payload": payload}) + "\n")

class MockHost:
    """Manages the agent interaction loop in the sandbox."""
    
    def __init__(self, workspace_root: Path, cli_name: str, dry_run: bool = False, model: str = None):
        self.workspace_root = workspace_root
        self.cli_name = cli_name
        self.dry_run = dry_run
        self.model = model
        self.plugin_dir = workspace_root / ".claude" / "harness-wf-plugin"
        self.config_dir = self.plugin_dir / "config"
        self.dispatcher = OrchestratorDispatcher(str(self.config_dir))
        self.tool_engine = ToolExecutionEngine(workspace_root)
        self.logger = HarnessEventLogger()
        # Set the instrumentation file path for the logger and hooks
        os.environ["HARNESS_INSTRUMENTATION_FILE"] = str(workspace_root / "sandbox_events.json")
        self.logger.log_file = os.environ["HARNESS_INSTRUMENTATION_FILE"]
        
        self.history = []

    HOOK_ALIASES = {
        "prompt_interceptor": "prompt_classifier",
        "pre_tool_guard": "pre_tool_guard",
        "post_tool_monitor": "post_tool_observer",
    }

    def run_hook(self, hook_module: str, input_data: Dict[str, Any]) -> str:
        """Run a hook via subprocess to simulate real Claude Code behavior."""
        hook_name = self.HOOK_ALIASES.get(hook_module, hook_module)
        hook_path = self.plugin_dir / "hooks" / f"{hook_name}.py"
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(self.plugin_dir)
        env["CLAUDE_PROJECT_DIR"] = str(self.workspace_root)
        
        proc = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(input_data),
            env=env,
            capture_output=True,
            text=True
        )
        if proc.stderr and "[VIOLATION]" in proc.stderr:
             self.logger.log_event("SAFETY_VIOLATION", {
                 "hook": hook_module,
                 "reason": proc.stderr,
                 "tool_name": input_data.get("tool_name"),
                 "tool_args": input_data.get("tool_args")
             })
             return f"HOOK_REJECTION: {proc.stderr}"
        if proc.returncode != 0:
             return f"HOOK_REJECTION: {proc.stderr}"
        return proc.stdout.strip()

    def run_task(self, user_prompt: str):
        print(f"--- Starting Task: {user_prompt} ---")
        self.logger.log_event("SESSION_START", {"prompt": user_prompt})
        
        # 1. Run prompt_interceptor
        modified_prompt = self.run_hook("prompt_interceptor", {"prompt": user_prompt})
        print(f"Intercepted Prompt: {modified_prompt[:100]}...")
        
        self.history.append({"role": "user", "content": modified_prompt})
        
        # Loop until completion or max turns
        try:
            for turn in range(20):
                print(f"--- Turn {turn+1} ---")
                
                # 2. Get LLM response
                if self.dry_run:
                    # In dry run, simulate a fixed sequence of agent turns
                    dry_run_turns = [
                        '{"tool": "read_file", "arguments": {"file_path": "app.py"}}',
                        '{"tool": "write_file", "arguments": {"file_path": "app.py", "content": "def hello():\\n    \\"\\"\\"Hello docstring\\"\\"\\"\\n    print(\'hello world\')\\n"}}',
                        'I am done'
                    ]
                    response_text = dry_run_turns[turn] if turn < len(dry_run_turns) else "I am done"
                else:
                    # Construct a prompt that includes history and tool instructions
                    full_prompt = self._build_llm_prompt()
                    # Ensure api_key is passed correctly. If it's missing, query_llm will handle it (usually by checking env)
                    response_text = query_llm(full_prompt, self.cli_name, model=self.model) or ""
                
                self.logger.log_event("LLM_RESPONSE", {"text": response_text})
                
                # 3. Parse tool calls
                tool_calls = self._parse_tool_calls(response_text)
                
                if tool_calls:
                    self.history.append({"role": "assistant", "content": response_text})
                    
                    for tool_call in tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["arguments"]
                        print(f"Tool Call: {tool_name}({tool_args})")
                        
                        # 4. Run pre_tool_guard
                        guard_result = self.run_hook("pre_tool_guard", {
                            "tool_name": tool_name,
                            "tool_args": tool_args
                        })
                        
                        if guard_result.startswith("HOOK_REJECTION:"):
                            print(f"Guard Rejected: {guard_result}")
                            self.history.append({"role": "user", "content": guard_result})
                            continue
                        
                        # 5. Execute tool
                        self.logger.log_event("TOOL", {
                            "tool_name": tool_name,
                            "tool_args": tool_args
                        })
                        tool_result = self._execute_tool(tool_name, tool_args)
                        print(f"Tool Result: {str(tool_result)[:100]}...")
                        
                        # 6. Run post_tool_monitor
                        self.run_hook("post_tool_monitor", {
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "result": tool_result
                        })
                        
                        self.history.append({"role": "user", "content": f"Tool Result ({tool_name}): {json.dumps(tool_result)}"})
                else:
                    # Agent finished or just talking
                    print(f"Assistant: {response_text}")
                    self.history.append({"role": "assistant", "content": response_text})
                    
                    if "I am done" in response_text or "Task complete" in response_text or turn > 15:
                        break
        finally:
            self.logger.log_event("SESSION_END", {"status": "finished"})
            print("--- Task Finished ---")
            
            # Generate final report
            events_file_path = os.environ.get("HARNESS_INSTRUMENTATION_FILE")
            if events_file_path:
                # We only need to trigger the generation; copying is no longer needed
                # as all sections write to the same master report.
                temp_artifacts_dir = self.workspace_root / "artifacts"
                temp_artifacts_dir.mkdir(parents=True, exist_ok=True)
                temp_output_report = temp_artifacts_dir / "sandbox_stats.md"
                # generate_report(events_file_path, str(temp_output_report))
                temp_output_report.write_text("# Mock Report")
                print("Master report updated with sandbox results.")

    def _build_llm_prompt(self) -> str:
        # Simple prompt construction for MockHost
        system_prompt = (
            "You are a helpful AI assistant. "
            "You have access to tools: read_file, write_file, replace, grep_search, run_shell_command, glob. "
            "To use a tool, output a JSON block like: {\"tool\": \"name\", \"arguments\": {...}}. "
            "When you are finished, say 'I am done'."
        )
        
        prompt_parts = [system_prompt]
        for msg in self.history:
            prompt_parts.append(f"{msg['role'].upper()}: {msg['content']}")
        
        prompt_parts.append("ASSISTANT:")
        return "\n\n".join(prompt_parts)

    def _parse_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Robustly parse multiple tool calls from text."""
        results = []
        i = 0
        while i < len(text):
            if text[i] == '{':
                start_idx = i
                brace_count = 1
                j = i + 1
                while j < len(text) and brace_count > 0:
                    if text[j] == '{':
                        brace_count += 1
                    elif text[j] == '}':
                        brace_count -= 1
                    j += 1
                
                if brace_count == 0:
                    potential_json = text[start_idx:j]
                    try:
                        data = json.loads(potential_json)
                        # Check if it looks like a tool call
                        name = data.get("tool") or data.get("name") or data.get("call")
                        args = data.get("arguments") or data.get("args") or data.get("input") or data.get("parameters") or {}
                        if name:
                            results.append({"name": name, "arguments": args})
                    except json.JSONDecodeError:
                        pass
                    i = j - 1
            i += 1
        return results

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> Any:
        try:
            # Normalize tool name
            name_map = {
                "Read": "read_file",
                "Write": "write_file",
                "Edit": "replace",
                "Grep": "grep_search",
                "Bash": "run_shell_command",
                "Glob": "glob"
            }
            normalized_name = name_map.get(name, name)
            
            if normalized_name == "read_file":
                return self.tool_engine.read_file(**args)
            elif normalized_name == "write_file":
                return self.tool_engine.write_file(**args)
            elif normalized_name == "replace":
                return self.tool_engine.replace(**args)
            elif normalized_name == "grep_search":
                return self.tool_engine.grep_search(**args)
            elif normalized_name == "run_shell_command":
                return self.tool_engine.run_shell_command(**args)
            elif normalized_name == "glob":
                return self.tool_engine.glob(**args)
            elif normalized_name == "Task":
                return self.tool_engine.task(args.get("agent_name"), args.get("prompt"), self.dispatcher)
            else:
                return f"Error: Tool {normalized_name} not found."
        except Exception as e:
            return f"Error executing tool {name}: {str(e)}"

def _print_score_report(scenario_name: str, result: dict, config_id: Optional[str] = None):
    """Print a human-readable score summary after a run."""
    print("\n" + "=" * 50)
    print(f"SCORE REPORT — {scenario_name}")
    if config_id:
        print(f"Config ID: {config_id}")
    print("-" * 50)
    for check, score in result["scores"].items():
        status = "PASS" if score >= 0.7 else "FAIL"
        print(f"  {check:<20} {score:.2f}  [{status}]")
    if result["skipped"]:
        print(f"  Skipped (no expected): {', '.join(result['skipped'])}")
    print("-" * 50)
    agg = result["aggregate"]
    verdict = "PASS" if result["passed"] else "FAIL"
    agg_str = f"{agg:.2f}" if agg is not None else "N/A"
    print(f"  Aggregate: {agg_str}  [{verdict}]")
    print("=" * 50 + "\n")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", help="Scenario name (looks in tests/sandbox/scenarios/)")
    parser.add_argument("--scenario-file", help="Path to a specific scenario YAML file")
    parser.add_argument("--list", action="store_true", help="List available scenarios")
    parser.add_argument("--provider", help="LLM provider (gemini, anthropic, openai)")
    parser.add_argument("--model", help="Specific model to use (e.g. gemini-flash-latest, gpt-4o)")
    parser.add_argument("--api-key", help="API key for the provider")
    parser.add_argument("--dry-run", action="store_true", help="Run without calling real LLM")
    parser.add_argument("--score", action="store_true",
                        help="Score the run against expected_behavior (if defined in scenario)")
    parser.add_argument("--config-id", default=None,
                        help="Harness config fingerprint for Langfuse run_name tagging "
                             "(use scripts/harness_config_id.py to generate)")
    args = parser.parse_args()

    if args.list:
        scenarios = list_scenarios()
        print("Available scenarios:")
        for s in scenarios:
            print(f"  - {s}")
        sys.exit(0)

    # Load scenario data
    scenario_data = None
    if args.scenario_file:
        scenario_data = load_scenario(Path(args.scenario_file))
    elif args.scenario:
        # Support captured/ prefix: --scenario captured/my_scenario
        scenario_path = Path(project_root) / "tests" / "sandbox" / "scenarios" / f"{args.scenario}.yaml"
        if not scenario_path.exists():
            print(f"Error: Scenario '{args.scenario}' not found at {scenario_path}")
            sys.exit(1)
        scenario_data = load_scenario(scenario_path)
    else:
        # Default to docstring if nothing provided
        scenario_path = Path(project_root) / "tests" / "sandbox" / "scenarios" / "docstring.yaml"
        if scenario_path.exists():
            scenario_data = load_scenario(scenario_path)
        else:
            print("Error: No scenario provided and default docstring.yaml not found.")
            sys.exit(1)

    prompt = scenario_data.get("prompt", "No prompt provided in scenario.")

    # Determine provider (cli_name)
    provider = args.provider
    if not provider:
        provider = "gemini" # Default
        
    if provider not in ["gemini", "claude"]:
        print(f"Warning: provider '{provider}' may not be supported by native_cli. Falling back to gemini")
        provider = "gemini"

    # Robust model selection
    model = args.model
    if not model and provider == "gemini":
        model = "gemini-2.5-flash-lite"

    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        print(f"Sandbox workspace: {workspace}")
        
        # 1. Setup scenario files
        setup_scenario_from_data(scenario_data, workspace)
        
        # 2. Mint harness
        os.environ["HARNESS_HEADLESS"] = "1"
        mint_harness(str(workspace), "SampleApp", model=model)
        
        # 3. Initialize MockHost
        host = MockHost(workspace, provider, dry_run=args.dry_run, model=model)
        
        # 4. Run task
        if args.config_id:
            os.environ["HARNESS_CONFIG_ID"] = args.config_id

        host.run_task(prompt)

        # 5. Check events
        events_file = workspace / "sandbox_events.json"
        if events_file.exists():
            print(f"Events captured in {events_file}")
            with open(events_file, 'r') as f:
                event_count = len(f.readlines())
                print(f"Total events: {event_count}")

        # 6. Score (only if --score and scenario defines expected_behavior)
        if args.score:
            expected_behavior = scenario_data.get("expected_behavior")
            scorer = ScenarioScorer(workspace, events_file, expected_behavior)
            result = scorer.score_all()
            _print_score_report(scenario_data.get("name", "unknown"), result, args.config_id)

if __name__ == "__main__":
    main()
