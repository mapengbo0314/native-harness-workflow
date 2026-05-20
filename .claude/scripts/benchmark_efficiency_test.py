#!/usr/bin/env python3
# DEPRECATED: Use efficiency_suite.py instead
"""
Token Efficiency Benchmark Utility

This script measures the token savings of the Agentic Harness (Hub-and-Spoke model)
vs. a Monolithic agent. It operates by simulating the actual CLI execution of the
agents and calculating the precise token usage across single or multi-task sessions.

Usage:
  python scripts/benchmark_efficiency_test.py --baseline
  python scripts/benchmark_efficiency_test.py --multi
  python scripts/benchmark_efficiency_test.py --prompt "Your custom task here"
"""

import os
import argparse
import sys
import subprocess
from pathlib import Path
from google import genai

# ==========================================
# 1. Token Utilities
# ==========================================

_CLIENT_CACHE = {}

def get_client(api_key: str) -> genai.Client:
    """Returns a cached genai.Client instance for the given API key."""
    if api_key not in _CLIENT_CACHE:
        _CLIENT_CACHE[api_key] = genai.Client(api_key=api_key)
    return _CLIENT_CACHE[api_key]

def count_tokens(text: str, model: str = "gemini-1.5-flash") -> int:
    if not text:
        return 0

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Fallback to rough estimation if no key (chars / 4, min 1 for non-empty)
        return max(1, len(text) // 4)
    
    try:
        client = get_client(api_key)
        response = client.models.count_tokens(
            model=model,
            contents=text
        )
        return response.total_tokens
    except Exception:
        return max(1, len(text) // 4)

# ==========================================
# 2. CLI Runner
# ==========================================

class CLIRunnerError(Exception):
    """Exception raised when a CLI command fails."""
    pass

def run_cli_command(cli_binary: str, args: list[str]) -> str:
    """
    Executes a cli command and returns the STDOUT.
    """
    cmd = [cli_binary] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except FileNotFoundError:
        error_msg = f"The '{cli_binary}' executable was not found in the system PATH."
        print(error_msg, file=sys.stderr)
        raise CLIRunnerError(error_msg)
    except subprocess.CalledProcessError as e:
        error_msg = f"Command '{' '.join(cmd)}' failed with exit code {e.returncode}: {e.stderr.strip()}"
        print(error_msg, file=sys.stderr)
        raise CLIRunnerError(error_msg) from e

# ==========================================
# 3. Benchmark Logic
# ==========================================

BASELINE_SINGLE = "Generate a JSON with 10 user objects (id, name, age). Filter those > 18. Output the result."

BASELINE_MULTI = [
    "Read the repository and generate a JSON array of 10 mock user objects (id, name, age, active). Return only the JSON.",
    "Filter the generated users to only include those where age > 18 and active is true.",
    "Add a new field 'role: admin' to the first two filtered users, and 'role: user' to the rest.",
    "Format the final processed list into a neat markdown table and write it to output.md."
]

def run_multi_benchmark(tasks: list[str], rules_content: str, harness_dir: Path):
    print(f"Starting Multi-Task Benchmark ({len(tasks)} sequential iterations)...\n")
    
    # Load actual agent prompts from disk to ground the token counts
    orch_path = harness_dir / "orchestrator.md"
    arch_path = harness_dir / "agents" / "architect.md"
    impl_path = harness_dir / "agents" / "implementer.md"
    
    orch_base = orch_path.read_text() if orch_path.exists() else "Orchestrator prompt"
    arch_base = arch_path.read_text() if arch_path.exists() else "Architect prompt"
    impl_base = impl_path.read_text() if impl_path.exists() else "Implementer prompt"
    
    # A monolithic agent needs all instructions (rules + orchestration + all skills/roles)
    mono_base = f"{rules_content}\n\n{orch_base}\n\n{arch_base}\n\n{impl_base}"
    
    mono_results = []
    harness_results = []
    mono_total = 0
    harness_total = 0
    
    # --- 1. Monolithic Agent ---
    print("=== Running Monolithic Benchmark (Accumulating Context) ===")
    history = mono_base
    for i, task in enumerate(tasks, 1):
        print(f"  Executing Task {i}/{len(tasks)}...")
        
        # Simulate reading a large file (approx 2000 tokens) during the task
        file_read_simulation = "file content " * 1000 
        
        prompt = f"{history}\n\nUser: {task}\nAssistant: ToolCall: read_file('app.py')\nSystem: {file_read_simulation}\nAssistant:"
        
        in_tokens = count_tokens(prompt)
        # Simulate the monolith doing real work (e.g., writing a 500-token code block/response)
        output = f"I have processed task {i}: {task}. Here is the output.\n" + ("code\n" * 150)
        out_tokens = count_tokens(output)
        
        task_tokens = in_tokens + out_tokens
        mono_results.append((in_tokens, out_tokens, task_tokens))
        mono_total += task_tokens
        
        # The monolith remembers the ENTIRE conversation (input + file reads + massive output)
        history += f"\n\nUser: {task}\nAssistant: ToolCall: read_file('app.py')\nSystem: {file_read_simulation}\nAssistant: {output}"

    # --- 2. Hub-and-Spoke (Orchestrator) ---
    print("\n=== Running Harness Benchmark (Isolated Subagents) ===")
    orchestrator_history = orch_base

    for i, task in enumerate(tasks, 1):
        print(f"  Executing Task {i}/{len(tasks)}...")
        
        # Simulate reading a large file (approx 2000 tokens)
        file_read_simulation = "file content " * 1000 
        
        # A. Orchestrator reads history + new task
        orch_prompt = f"{orchestrator_history}\n\nUser: {task}"
        orch_in_tokens = count_tokens(orch_prompt)
        
        # B. Architect (Fresh context per task: rules + role + task + file reads)
        arch_prompt = f"{rules_content}\n\n{arch_base}\n\nTASK: {task}\nAssistant: ToolCall: read_file('app.py')\nSystem: {file_read_simulation}"
        arch_in_tokens = count_tokens(arch_prompt)
        # Architect outputs a concise plan
        arch_output = f"Architect parsed: {task}. Proceed with step 1, 2, 3.\n" + ("plan\n" * 50)
        arch_out_tokens = count_tokens(arch_output)
        
        # C. Implementer (Fresh context: rules + role + Architect's summary + task)
        impl_prompt = f"{rules_content}\n\n{impl_base}\n\nSummary of research: {arch_output}\n\nTask: {task}"
        impl_in_tokens = count_tokens(impl_prompt)
        # Implementer outputs the actual code
        impl_output = f"Implementation complete for: {task}\n" + ("code\n" * 150)
        impl_out_tokens = count_tokens(impl_output)
        
        # D. Orchestrator responds (saves tiny summary to its history, not the massive code block)
        orch_response = f"Delegated. Result snippet: {impl_output[:150]}..."
        orch_out_tokens = count_tokens(orch_response)
        
        task_tokens = orch_in_tokens + arch_in_tokens + arch_out_tokens + impl_in_tokens + impl_out_tokens + orch_out_tokens
        harness_results.append({
            "orch_in": orch_in_tokens, "arch_in": arch_in_tokens, "arch_out": arch_out_tokens,
            "impl_in": impl_in_tokens, "impl_out": impl_out_tokens, "orch_out": orch_out_tokens,
            "total": task_tokens
        })
        harness_total += task_tokens
        
        # The orchestrator ONLY remembers the user's prompt and its tiny summary, never the raw code/output
        orchestrator_history += f"\n\nUser: {task}\nAssistant: {orch_response}"

    # --- 3. Results ---
    print("\n" + "="*70)
    print("MULTI-TASK BENCHMARK RESULTS")
    print("="*70)
    print(f"{'Task':<10} | {'Monolith Tokens':<25} | {'Harness Tokens':<25}")
    print("-" * 70)
    for i in range(len(tasks)):
        m_tot = mono_results[i][2]
        h_tot = harness_results[i]["total"]
        print(f"Task {i+1:<5} | {m_tot:<25,} | {h_tot:<25,}")
        
    print("-" * 70)
    print(f"{'TOTAL':<10} | {mono_total:<25,} | {harness_total:<25,}")
    
    if mono_total > 0:
        savings = (1 - (harness_total / mono_total)) * 100
        print(f"\nOverall Token Savings: {savings:.1f}%")
    print("="*70)
    
    print("\nHarness Detailed Breakdown per Task:")
    for i, res in enumerate(harness_results, 1):
        print(f"Task {i}: Orch({res['orch_in']}+{res['orch_out']}) + Arch({res['arch_in']}+{res['arch_out']}) + Impl({res['impl_in']}+{res['impl_out']}) = {res['total']}")


def run_monolith_benchmark(task_prompt: str, rules_content: str, cli_tool: str = "gemini"):
    full_prompt = f"Instructions:\n{rules_content}\n\nTASK: {task_prompt}"
    
    print("Running Monolith Benchmark...")
    input_tokens = count_tokens(full_prompt)
    
    try:
        # Using -p for non-interactive prompt mode
        args = ["-p", f"You are a monolithic agent. Read these instructions:\n\n{rules_content}\n\nTask: {task_prompt}"]
        if cli_tool == "gemini":
            args = ["-y"] + args
        output = run_cli_command(cli_tool, args)
        output_tokens = count_tokens(output)
    except Exception as e:
        print(f"Warning: CLI call failed, using estimation for output tokens. Error: {e}")
        output_tokens = count_tokens("Simulated monolith output")
            
    return input_tokens + output_tokens

def run_harness_benchmark(task_prompt: str, harness_dir: Path, cli_tool: str = "gemini"):
    rules_path = harness_dir / "rules" / "core_mandates.md"
    rules_content = rules_path.read_text() if rules_path.exists() else ""
    
    architect_agent_path = harness_dir / "agents" / "architect.md"
    implementer_agent_path = harness_dir / "agents" / "implementer.md"
    
    arch_base = architect_agent_path.read_text() if architect_agent_path.exists() else "Architect prompt"
    impl_base = implementer_agent_path.read_text() if implementer_agent_path.exists() else "Implementer prompt"
    
    print("Running Harness Step 1: Architect...")
    # Architect input = rules + architect role + task
    arch_input_full = f"{rules_content}\n\n{arch_base}\n\nTASK: {task_prompt}"
    architect_input_tokens = count_tokens(arch_input_full)
    
    try:
        args = ["-p", f"Role: Architect\n\nInstructions:\n{rules_content}\n\n{arch_base}\n\nTask: {task_prompt}"]
        if cli_tool == "gemini":
            args = ["-y"] + args
        arch_output = run_cli_command(cli_tool, args)
    except Exception as e:
        print(f"Warning: Architect CLI call failed, using estimation. Error: {e}")
        arch_output = "Simulated architect plan"
        
    arch_out_tokens = count_tokens(arch_output)
    
    print("Running Harness Step 2: Implementer...")
    # Implementer input = rules + implementer role + architect summary + task
    impl_input_full = f"{rules_content}\n\n{impl_base}\n\nSummary of research: {arch_output}\n\nTask: {task_prompt}"
    impl_input_tokens = count_tokens(impl_input_full)
    
    try:
        args = ["-p", f"Role: Implementer\n\nInstructions:\n{rules_content}\n\n{impl_base}\n\nSummary of research: {arch_output}\n\nTask: {task_prompt}"]
        if cli_tool == "gemini":
            args = ["-y"] + args
        impl_output = run_cli_command(cli_tool, args)
    except Exception as e:
        print(f"Warning: Implementer CLI call failed, using estimation. Error: {e}")
        impl_output = "Simulated implementation output"
        
    impl_out_tokens = count_tokens(impl_output)
    
    total_tokens = architect_input_tokens + arch_out_tokens + impl_input_tokens + impl_out_tokens
    return total_tokens

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true", help="Run the single-task baseline")
    parser.add_argument("--multi", action="store_true", help="Run the multi-task (4 iterations) benchmark")
    parser.add_argument("--prompt", type=str, help="Run a custom single task")
    parser.add_argument("--cli", type=str, default="gemini", choices=["gemini", "claude"], help="CLI binary to run")
    args = parser.parse_args()
    
    if not (args.baseline or args.multi or args.prompt):
        print("Please provide --baseline, --multi, or --prompt")
        return

    script_dir = Path(__file__).parent.resolve()
    harness_dir = script_dir.parent
    
    rules_path = harness_dir / "rules" / "core_mandates.md"
    try:
        with open(rules_path, "r") as f:
            rules = f.read()
    except FileNotFoundError:
        rules = "# Core Rules\n1. Do good code."
        print(f"Warning: {rules_path} not found. Using fallback rules.")

    try:
        if args.multi:
            run_multi_benchmark(BASELINE_MULTI, rules, harness_dir)
        else:
            task = args.prompt or BASELINE_SINGLE
            monolith_total = run_monolith_benchmark(task, rules, args.cli)
            harness_total = run_harness_benchmark(task, harness_dir, args.cli)
            
            print("\n" + "="*30)
            print("SINGLE TASK RESULTS")
            print(f"Task: {task[:50]}...")
            print(f"Monolith: {monolith_total} tokens")
            print(f"Harness:  {harness_total} tokens")
            if monolith_total > 0:
                savings = (1 - (harness_total / monolith_total)) * 100
                print(f"Savings:  {savings:.1f}%")
            print("="*30)
            
    except CLIRunnerError as e:
        print(f"\nBenchmark failed due to CLI error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
