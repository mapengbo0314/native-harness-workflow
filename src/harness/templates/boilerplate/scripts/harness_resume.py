# src/harness/templates/boilerplate/scripts/harness_resume.py
import sys
from pathlib import Path

plugin_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(plugin_root / "hooks"))

from hook_common import resolve_state_path, read_json

def main():
    state_path = resolve_state_path()
    state = read_json(state_path)
    
    tasks = state.get("tasks", {})
    goal = tasks.get("current_goal", "No active goal")
    steps = tasks.get("steps", [])
    
    output = []
    output.append(f"### Current Goal: {goal}")
    output.append("### Steps:")
    
    if not steps:
        output.append("No steps defined.")
    else:
        for step in steps:
            mark = "x" if step.get("status") == "completed" else " "
            output.append(f"- [{mark}] {step.get('name')}")
            
    # Combine and cap summary at 1000 characters
    summary = "\n".join(output)
    if len(summary) > 1000:
        summary = summary[:997] + "..."
        
    print(summary)

if __name__ == "__main__":
    main()