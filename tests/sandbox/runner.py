import os
import json
import subprocess
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
import xml.sax.saxutils

# Add src and project root to sys.path to import harness and sandbox components
project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

from harness.dispatcher import OrchestratorDispatcher
from harness.discovery_engine import query_llm
from harness.instrumentation import HarnessEventLogger
from harness.minting_engine import mint_workspace, synthesize_domain_sme_agent, patch_orchestrator_rules
from harness.plugin_generator import generate_orchestrator_plugin
from tests.sandbox.analytics import generate_report

def mint_harness(project_path: str, project_name: str):
    """Simplified minting for sandbox runner."""
    project_path = Path(project_path)
    harness_folder = ".claude"
    target_dir = project_path / harness_folder
    
    # Use absolute path for boilerplate to be robust to execution directory
    boilerplate_dir = str(Path(project_root) / "src" / "harness" / "templates" / "boilerplate")
    
    # Create minimal docs/domain/CONTEXT.md if it doesn't exist
    context_dir = project_path / "docs" / "domain"
    context_dir.mkdir(parents=True, exist_ok=True)
    context_file = context_dir / "CONTEXT.md"
    if not context_file.exists():
        context_file.write_text("# Project Context\n\n## Purpose\nSandbox Test\n\n## Ubiquitous Language\nNone\n\n## Strict Invariants\nNone\n")

    # Mock domain content for SME synthesis
    domain_content = "Proposed Agent Name: @domain-sme\nDomain Invariants:\nNone\nUbiquitous Language:\nNone\n- [x] orchestrator-plugin (local)"
    
    # Mint workspace
    mint_workspace(str(target_dir), [], str(project_path), "2", boilerplate_dir=boilerplate_dir)
    
    # Synthesize SME
    sme_name = synthesize_domain_sme_agent(str(project_path), domain_content, harness_folder, platform_choice="2")
    patch_orchestrator_rules(str(project_path), sme_name, harness_folder, target_syntax="Task tool: ")
    
    # Generate plugin
    generate_orchestrator_plugin(str(project_path), project_name, boilerplate_dir=boilerplate_dir)

class ToolExecutionEngine:
    """Simulates Claude Code tools in a sandbox environment."""
    
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    def read_file(self, file_path: str, start_line: int = None, end_line: int = None) -> str:
        full_path = self.workspace_root / file_path
        if not full_path.exists():
            return f"Error: File {file_path} not found."
        
        with open(full_path, 'r') as f:
            lines = f.readlines()
        
        start = (start_line - 1) if start_line else 0
        end = end_line if end_line else len(lines)
        return "".join(lines[start:end])

    def write_file(self, file_path: str, content: str) -> str:
        full_path = self.workspace_root / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"

    def replace(self, file_path: str, old_string: str, new_string: str, instruction: str = "") -> str:
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

    def grep_search(self, pattern: str, include_pattern: str = None) -> str:
        cmd = ["grep", "-rn", pattern, "."]
        if include_pattern:
            cmd.extend(["--include", include_pattern])
        
        result = subprocess.run(cmd, cwd=self.workspace_root, capture_output=True, text=True)
        return result.stdout if result.stdout else "No matches found."

    def run_shell_command(self, command: str) -> Dict[str, Any]:
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

class MockHost:
    """Manages the agent interaction loop in the sandbox."""
    
    def __init__(self, workspace_root: Path, api_key: str, llm_provider: str = "anthropic", dry_run: bool = False):
        self.workspace_root = workspace_root
        self.api_key = api_key
        self.llm_provider = llm_provider
        self.dry_run = dry_run
        self.plugin_dir = workspace_root / ".claude" / "plugin-generated"
        self.config_dir = self.plugin_dir / "config"
        self.dispatcher = OrchestratorDispatcher(str(self.config_dir))
        self.tool_engine = ToolExecutionEngine(workspace_root)
        self.logger = HarnessEventLogger()
        # Set the instrumentation file path for the logger and hooks
        os.environ["HARNESS_INSTRUMENTATION_FILE"] = str(workspace_root / "sandbox_events.json")
        self.logger.log_file = os.environ["HARNESS_INSTRUMENTATION_FILE"]
        
        self.history = []

    def run_hook(self, hook_module: str, input_data: Dict[str, Any]) -> str:
        """Run a hook via subprocess to simulate real Claude Code behavior."""
        hook_path = self.plugin_dir / "src" / "hooks" / f"{hook_module}.py"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.plugin_dir / "src")
        
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
                    response_text = query_llm(full_prompt, self.llm_provider, self.api_key)
                
                self.logger.log_event("LLM_RESPONSE", {"text": response_text})
                
                # 3. Parse tool calls
                tool_call = self._parse_tool_call(response_text)
                
                if tool_call:
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
                        self.history.append({"role": "assistant", "content": response_text})
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
                    
                    self.history.append({"role": "assistant", "content": response_text})
                    self.history.append({"role": "user", "content": f"Tool Result: {json.dumps(tool_result)}"})
                else:
                    # Agent finished or just talking
                    print(f"Assistant: {response_text}")
                    self.history.append({"role": "assistant", "content": response_text})
                    
                    if "I am done" in response_text or "Task complete" in response_text or turn > 15:
                        # 7. Run stop_monitor
                        stop_result = self.run_hook("stop_monitor", {"reason": "completed"})
                        if stop_result.startswith("HOOK_REJECTION:"):
                            print(f"Stop Monitor Rejected: {stop_result}")
                            self.history.append({"role": "user", "content": stop_result})
                            continue
                        break
        finally:
            self.logger.log_event("SESSION_END", {"status": "finished"})
            print("--- Task Finished ---")
            
            # Generate final report
            events_file_path = os.environ.get("HARNESS_INSTRUMENTATION_FILE")
            if events_file_path:
                # 1. Generate report in temp workspace
                temp_artifacts_dir = self.workspace_root / "artifacts"
                temp_artifacts_dir.mkdir(parents=True, exist_ok=True)
                temp_output_report = temp_artifacts_dir / "sandbox_stats.md"
                generate_report(events_file_path, str(temp_output_report))

                # 2. Copy to project root artifacts/
                project_artifacts = Path(project_root) / "artifacts"
                project_artifacts.mkdir(parents=True, exist_ok=True)
                
                shutil.copy2(temp_output_report, project_artifacts / "sandbox_stats.md")
                shutil.copy2(events_file_path, project_artifacts / "sandbox_events.json")
                print(f"Artifacts copied to {project_artifacts}")

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

    def _parse_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        # More robust tool call parser using brace counting to handle nested JSON
        import re
        
        # Find start of potential JSON objects containing "tool" or "name"
        for start_match in re.finditer(r'\{(?:\s*"tool"|\s*"name")\s*:', text):
            start_idx = start_match.start()
            brace_count = 0
            for i in range(start_idx, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        potential_json = text[start_idx:i+1]
                        try:
                            data = json.loads(potential_json)
                            name = data.get("tool") or data.get("name")
                            args = data.get("arguments") or data.get("args") or data.get("input") or {}
                            if name:
                                return {"name": name, "arguments": args}
                        except json.JSONDecodeError:
                            continue
        return None

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> Any:
        if name == "read_file" or name == "Read":
            return self.tool_engine.read_file(**args)
        elif name == "write_file" or name == "Write":
            return self.tool_engine.write_file(**args)
        elif name == "replace" or name == "Edit":
            return self.tool_engine.replace(**args)
        elif name == "grep_search" or name == "Grep":
            return self.tool_engine.grep_search(**args)
        elif name == "run_shell_command" or name == "Bash":
            return self.tool_engine.run_shell_command(**args)
        elif name == "glob" or name == "Glob":
            return self.tool_engine.glob(**args)
        elif name == "Task":
            return self.tool_engine.task(args.get("agent_name"), args.get("prompt"), self.dispatcher)
        else:
            return f"Error: Tool {name} not found."

def setup_scenario(scenario: str, workspace: Path):
    """Setup a sample project for a scenario."""
    if scenario == "docstring":
        app_py = workspace / "app.py"
        app_py.write_text("def hello():\n    print('hello world')\n")
        
        tests_dir = workspace / "tests"
        tests_dir.mkdir(exist_ok=True)
        test_py = tests_dir / "test_app.py"
        test_py.write_text("from app import hello\ndef test_hello():\n    hello()\n")
    elif scenario == "bugfix":
        app_py = workspace / "app.py"
        app_py.write_text("def divide(a, b):\n    return a / b\n")
        
        tests_dir = workspace / "tests"
        tests_dir.mkdir(exist_ok=True)
        test_py = tests_dir / "test_app.py"
        test_py.write_text("from app import divide\nimport pytest\ndef test_divide():\n    assert divide(10, 2) == 5\n    with pytest.raises(ZeroDivisionError):\n        divide(10, 0)\n")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["docstring", "bugfix"], default="docstring")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--api-key", help="API key for the provider")
    parser.add_argument("--dry-run", action="store_true", help="Run without calling real LLM")
    args = parser.parse_args()

    # Use provided key or look in environment
    api_key = args.api_key
    if not api_key:
        if args.provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY", "")
        elif args.provider == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        elif args.provider == "gemini":
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""

    if not args.dry_run and not api_key:
        print(f"Error: API key for {args.provider} is required when not in --dry-run mode.")
        print(f"Please provide --api-key or set the appropriate environment variable.")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        print(f"Sandbox workspace: {workspace}")
        
        # 1. Setup scenario files
        setup_scenario(args.scenario, workspace)
        
        # 2. Mint harness
        os.environ["HARNESS_HEADLESS"] = "1"
        mint_harness(str(workspace), "SampleApp")
        
        # 3. Initialize MockHost
        host = MockHost(workspace, api_key, args.provider, dry_run=args.dry_run)
        
        # 4. Run task
        if args.scenario == "docstring":
            prompt = "Add a docstring to the hello function in app.py. Remember to follow TDD: write a failing test first."
        else:
            prompt = "Fix the potential ZeroDivisionError in the divide function in app.py. Follow TDD."
            
        host.run_task(prompt)
        
        # 5. Check events
        events_file = workspace / "sandbox_events.json"
        if events_file.exists():
            print(f"Events captured in {events_file}")
            with open(events_file, 'r') as f:
                event_count = len(f.readlines())
                print(f"Total events: {event_count}")

if __name__ == "__main__":
    main()
