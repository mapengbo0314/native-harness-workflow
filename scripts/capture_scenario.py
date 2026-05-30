#!/usr/bin/env python3
"""
Capture a harness failure from a real session into a replayable sandbox scenario.

Reads logs/pre_tool_use.json (the hook event log written by the harness), identifies
which files were touched in the target project, snapshots their current content, and
writes a scenario YAML to tests/sandbox/scenarios/captured/<name>.yaml.

Usage:
  python scripts/capture_scenario.py \\
    --project ../bz \\
    --name auth_routing_miss \\
    --failure-type routing \\
    --severity high \\
    --expected-branch D \\
    --description "Agent routed rename-component task to branch C instead of D"

The prompt is read from --prompt or interactively from stdin.

The generated YAML is backward-compatible with the existing sandbox runner and also
carries the richer fields (failure_type, tech_stack, expected_behavior) that the
scorer uses when --score is passed to runner.py.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent.resolve()
DEFAULT_LOG_FILE = REPO_ROOT / "logs" / "pre_tool_use.json"
CAPTURED_DIR = REPO_ROOT / "tests" / "sandbox" / "scenarios" / "captured"

KNOWN_FAILURE_TYPES = ["routing", "workflow", "output", "loop", "instruction", "unknown"]
KNOWN_BRANCHES = ["A", "B", "C", "D", "E"]

BRANCH_TO_AGENT = {
    "A": "debugger",
    "B": "planner",
    "C": "generalist",
    "D": "implementer",
    "E": None,
}

FILE_TOOLS = {
    "read", "read_file",
    "write", "write_file",
    "edit", "replace", "multiedit",
}

TECH_STACK_INDICATORS = [
    ("typescript", ["tsconfig.json"]),
    ("javascript", ["package.json"]),
    ("python", ["pyproject.toml", "setup.py", "requirements.txt"]),
    ("playwright", ["playwright.config.ts", "playwright.config.js"]),
    ("nextjs", ["next.config.js", "next.config.ts", "next.config.mjs"]),
    ("react", []),      # detected via file extensions below
    ("fastapi", ["main.py"]),
    ("django", ["manage.py"]),
]


def load_log(log_path: Path) -> list:
    if not log_path.exists():
        return []
    with open(log_path) as f:
        content = f.read().strip()
    if not content:
        return []
    if content.startswith("["):
        return json.loads(content)
    # Newline-delimited JSON fallback
    events = []
    for line in content.splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def filter_by_project(events: list, project_root: Path) -> list:
    """Keep only events whose cwd is inside the target project."""
    project_str = str(project_root)
    return [e for e in events if str(e.get("cwd", "")).startswith(project_str)]


def extract_touched_files(events: list, project_root: Path) -> dict:
    """
    Walk events and collect files that were read or written inside project_root.
    Returns {relative_path: content}.
    """
    touched = set()
    for event in events:
        tool = event.get("tool_name", "").lower()
        if tool not in FILE_TOOLS:
            continue
        inp = event.get("tool_input") or {}
        path_val = inp.get("file_path") or inp.get("path") or inp.get("filename")
        if not path_val:
            continue
        candidate = Path(path_val)
        # Make relative to project root
        try:
            rel = candidate.relative_to(project_root)
        except ValueError:
            # Path not inside project_root — skip
            continue
        touched.add(rel)

    files = {}
    for rel in sorted(touched):
        full = project_root / rel
        if full.exists() and full.is_file():
            try:
                files[str(rel)] = full.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
    return files


def detect_tech_stack(project_root: Path) -> list:
    stack = []
    for tech, indicators in TECH_STACK_INDICATORS:
        for fname in indicators:
            if (project_root / fname).exists():
                stack.append(tech)
                break
    # Extension-based detection
    if not stack:
        if any(project_root.rglob("*.ts")) or any(project_root.rglob("*.tsx")):
            stack.append("typescript")
        if any(project_root.rglob("*.py")):
            stack.append("python")
    return list(dict.fromkeys(stack))


def build_scenario(
    name: str,
    prompt: str,
    files: dict,
    failure_type: str,
    severity: str,
    expected_branch: str,
    tech_stack: list,
    captured_from: str,
    description: str,
) -> dict:
    scenario = {
        "name": name,
        "source": "real_work",
        "severity": severity,
        "failure_type": failure_type,
        "tech_stack": tech_stack,
        "captured_from": captured_from,
        "captured_at": datetime.utcnow().strftime("%Y-%m-%d"),
        "description": description or f"Captured failure: {failure_type}",
        "prompt": prompt,
        "files": files,
    }
    if expected_branch:
        branch = expected_branch.upper()
        expected_behavior = {"branch": branch}
        agent = BRANCH_TO_AGENT.get(branch)
        if agent:
            expected_behavior["agent"] = agent
        scenario["expected_behavior"] = expected_behavior

    return scenario


def main():
    parser = argparse.ArgumentParser(
        description="Capture a real-work harness failure as a replayable sandbox scenario.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--project", required=True,
                        help="Path to the real project (e.g. ../bz)")
    parser.add_argument("--name", required=True,
                        help="Short slug for the scenario (e.g. auth_routing_miss)")
    parser.add_argument("--prompt", default=None,
                        help="The exact prompt that caused the failure (read from stdin if omitted)")
    parser.add_argument("--failure-type", default="unknown",
                        choices=KNOWN_FAILURE_TYPES,
                        help="Type of failure observed (default: unknown)")
    parser.add_argument("--severity", default="medium",
                        choices=["high", "medium", "low"])
    parser.add_argument("--expected-branch", choices=KNOWN_BRANCHES,
                        help="Branch the harness SHOULD have routed to (A/B/C/D/E)")
    parser.add_argument("--description", default="",
                        help="Short human-readable description of what went wrong")
    parser.add_argument("--log-file", default=str(DEFAULT_LOG_FILE),
                        help=f"Hook log file (default: {DEFAULT_LOG_FILE})")
    parser.add_argument("--no-snapshot", action="store_true",
                        help="Skip file snapshotting; write scenario with empty files dict")
    parser.add_argument("--tech-stack", nargs="+",
                        help="Override auto-detected tech stack (e.g. --tech-stack typescript playwright)")
    args = parser.parse_args()

    project_root = Path(args.project).resolve()
    if not project_root.exists():
        print(f"Error: project path does not exist: {project_root}", file=sys.stderr)
        sys.exit(1)

    # Prompt
    prompt = args.prompt
    if not prompt:
        print("Enter the prompt that caused the failure (Ctrl-D when done):")
        try:
            prompt = sys.stdin.read().strip()
        except KeyboardInterrupt:
            print("\nAborted.", file=sys.stderr)
            sys.exit(1)
    if not prompt:
        print("Error: prompt cannot be empty.", file=sys.stderr)
        sys.exit(1)

    # File snapshot
    files = {}
    if not args.no_snapshot:
        log_path = Path(args.log_file)
        all_events = load_log(log_path)
        project_events = filter_by_project(all_events, project_root)

        if project_events:
            files = extract_touched_files(project_events, project_root)
            if files:
                print(f"Snapshotted {len(files)} file(s) from {project_root}:")
                for fp in sorted(files):
                    print(f"  {fp}")
            else:
                print("Hook log has events for this project but no file paths could be resolved.")
                print("The scenario will have an empty files dict — add files manually.")
        elif all_events:
            print(f"Hook log has {len(all_events)} event(s) but none match project path {project_root}.")
            print("Use --no-snapshot to skip, or check --log-file path.")
        else:
            print(f"No events found in {log_path}.")
            print("Use --no-snapshot to skip, or check --log-file path.")

    tech_stack = args.tech_stack or detect_tech_stack(project_root)

    scenario = build_scenario(
        name=args.name,
        prompt=prompt,
        files=files,
        failure_type=args.failure_type,
        severity=args.severity,
        expected_branch=args.expected_branch,
        tech_stack=tech_stack,
        captured_from=project_root.name,
        description=args.description,
    )

    CAPTURED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CAPTURED_DIR / f"{args.name}.yaml"

    with open(out_path, "w") as f:
        yaml.dump(scenario, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"\nScenario written to: {out_path}")
    print("Review the files section before committing — truncate large files to the relevant parts.")


if __name__ == "__main__":
    main()
