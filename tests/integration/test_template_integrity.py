import os
import re
import yaml
from pathlib import Path
from tests.integration.test_platform_snapshots import temp_project, run_harness_init

def test_no_dangling_references_in_generated_templates(temp_project):
    run_harness_init(temp_project, "1")
    
    md_files = []
    for root, dirs, files in os.walk(temp_project):
        for file in files:
            if file.endswith(".md"):
                md_files.append(Path(root) / file)
                
    at_reference_regex = re.compile(r"@([a-zA-Z0-9_\-\./]+?\.md)")
    
    agents_dir = Path(temp_project) / ".gemini" / "agents"
    skills_dir = Path(temp_project) / ".gemini" / "skills"
    
    valid_agents = set()
    if agents_dir.exists():
        valid_agents = {f.stem for f in agents_dir.glob("*.md")}
        valid_agents.add("orchestrator")  # orchestrator.md is at root, but sometimes referred to. Let's add it.
        valid_agents.add("generalist") # built-in
        valid_agents.add("code-reviewer") # built-in
        
    valid_skills = set()
    if skills_dir.exists():
        valid_skills = {d.name for d in skills_dir.iterdir() if d.is_dir()}
        
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        
        # 1. explicit @ references
        for match in at_reference_regex.finditer(content):
            ref_path = match.group(1)
            target_file = (md_file.parent / ref_path).resolve()
            assert target_file.exists(), f"Dangling @ reference {match.group(0)} found in {md_file.relative_to(temp_project)}"
            
        # 2. YAML blocks
        frontmatter_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
        if frontmatter_match:
            try:
                fm = yaml.safe_load(frontmatter_match.group(1))
                if isinstance(fm, dict):
                    metadata = fm.get("metadata", {})
                    if isinstance(metadata, dict) and "related-skills" in metadata:
                        skills = metadata["related-skills"]
                        if isinstance(skills, str):
                            skills = [s.strip() for s in skills.split(",")]
                        for skill in skills:
                            assert skill in valid_skills, f"Dangling skill reference '{skill}' in frontmatter of {md_file.relative_to(temp_project)}"
            except Exception:
                pass
                
        yaml_blocks = re.findall(r'```yaml\n(.*?)\n```', content, re.DOTALL)
        for block in yaml_blocks:
            if "customization_config" in block:
                try:
                    cfg = yaml.safe_load(block)
                    agents_config = cfg.get("customization_config", {}).get("customization_discovery_config", {}).get("agents", {})
                    if "related_agents" in agents_config and agents_config["related_agents"]:
                        for agent in agents_config["related_agents"]:
                            assert agent in valid_agents, f"Dangling agent reference '{agent}' in yaml block of {md_file.relative_to(temp_project)}"
                except Exception:
                    pass

        # 3. Markdown lists
        metadata_section = re.search(r'## Metadata(.*?)(?:## |$)', content, re.DOTALL)
        if metadata_section:
            metadata_text = metadata_section.group(1)
            current_list = None
            for line in metadata_text.split("\n"):
                line = line.strip('\r')
                if line.startswith("- Skills:"):
                    current_list = "skills"
                elif line.startswith("- Related Agents:"):
                    current_list = "agents"
                elif line.startswith("- "):
                    current_list = None
                elif line.startswith("  - ") and current_list:
                    item = line.replace("  - ", "").strip()
                    if current_list == "skills":
                        assert item in valid_skills, f"Dangling skill reference '{item}' in markdown of {md_file.relative_to(temp_project)}"
                    elif current_list == "agents":
                        assert item in valid_agents, f"Dangling agent reference '{item}' in markdown of {md_file.relative_to(temp_project)}"
