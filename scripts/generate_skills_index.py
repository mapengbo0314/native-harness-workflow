import json
import os
from pathlib import Path

def generate_index():
    skills_dir = Path(".gemini/skills")
    index = {}
    
    if not skills_dir.exists():
        print(f"Skills directory not found at {skills_dir}")
        return

    for skill_path in skills_dir.glob("*/SKILL.md"):
        skill_name = skill_path.parent.name
        # Simple extraction of description if available
        content = skill_path.read_text()
        description = "No description available."
        for line in content.splitlines():
            if line.startswith("description:"):
                description = line.split("description:", 1)[1].strip()
                break
                
        index[skill_name] = {
            "path": str(skill_path),
            "description": description
        }
        
    index_path = Path(".gemini/skills_index.json")
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
    print(f"Generated {index_path} with {len(index)} skills.")

if __name__ == "__main__":
    generate_index()