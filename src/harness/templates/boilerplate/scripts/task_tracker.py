# src/harness/templates/boilerplate/scripts/task_tracker.py
import argparse
import sys
from pathlib import Path

# Add the hooks directory to sys.path so we can import hook_common
# scripts/ is a sibling to hooks/ in the generated plugin
plugin_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(plugin_root / "hooks"))

from hook_common import resolve_state_path, update_state

def main():
    parser = argparse.ArgumentParser(description="Deterministic task tracking.")
    parser.add_argument("--set-goal", type=str, help="Set the current goal")
    parser.add_argument("--add-step", type=str, help="Add a new step")
    parser.add_argument("--complete-step", type=str, help="Mark a step as completed")
    
    args = parser.parse_args()
    state_path = resolve_state_path()
    
    def modifier(data: dict):
        if "tasks" not in data:
            data["tasks"] = {"current_goal": "", "steps": []}
            
        if args.set_goal:
            data["tasks"]["current_goal"] = args.set_goal
        
        if args.add_step:
            # Prevent duplicates
            if not any(s["name"] == args.add_step for s in data["tasks"]["steps"]):
                data["tasks"]["steps"].append({"name": args.add_step, "status": "pending"})
                
        if args.complete_step:
            for step in data["tasks"]["steps"]:
                if step["name"] == args.complete_step:
                    step["status"] = "completed"
                    break

    update_state(state_path, modifier)

if __name__ == "__main__":
    main()