import json
import sys
from pathlib import Path

def find_project_root() -> Path:
    current = Path.cwd().resolve()
    while current != current.parent:
        if (current / ".gemini").exists():
            return current
        current = current.parent
    # Fallback to the directory containing this script (assuming it's in a subfolder like scripts/)
    return Path(__file__).resolve().parent.parent

def activate_skill(skill_name: str):
    root = find_project_root()
    index_path = root / ".gemini" / "skills_index.json"
    if not index_path.exists():
        print("Error: skills_index.json not found. Run generate_skills_index.py first.")
        sys.exit(1)
        
    with open(index_path, "r") as f:
        index = json.load(f)
        
    if skill_name not in index:
        print(f"Error: Skill '{skill_name}' not found in index.")
        print(f"Available skills: {', '.join(index.keys())}")
        sys.exit(1)
        
    skill_path_raw = Path(index[skill_name]["path"])
    if not skill_path_raw.is_absolute():
        skill_path = root / skill_path_raw
    else:
        skill_path = skill_path_raw
        
    if not skill_path.exists():
        print(f"Error: Skill file not found at {skill_path}")
        sys.exit(1)
        
    print(f"--- ACTIVE SKILL: {skill_name} ---")
    print(skill_path.read_text())
    print(f"--- END SKILL: {skill_name} ---")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python activate_skill.py <skill_name>")
        sys.exit(1)
    activate_skill(sys.argv[1])