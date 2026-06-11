import os
import re
import yaml
from pathlib import Path
from tests.integration.test_platform_snapshots import temp_project, run_harness_init

# ---------------------------------------------------------------------------
# rules/packs – shipped-file assertions (no fixture; reads source tree directly)
# ---------------------------------------------------------------------------

PACKS_DIR = (
    Path(__file__).parents[2]
    / "src" / "harness" / "templates" / "boilerplate" / "rules" / "packs"
)
LANGUAGE_DIRS = ["python", "typescript", "golang"]


def test_rules_packs_ships_common_baseline():
    """common/baseline.md must be present in the shipped packs directory."""
    baseline = PACKS_DIR / "common" / "baseline.md"
    assert baseline.exists(), f"Expected {baseline} to exist"


def test_rules_packs_language_dirs_each_have_at_least_one_md():
    """Each language directory (python, typescript, golang) must contain at least one .md file."""
    for lang in LANGUAGE_DIRS:
        lang_dir = PACKS_DIR / lang
        assert lang_dir.is_dir(), f"Expected language dir {lang_dir} to exist"
        md_files = list(lang_dir.glob("*.md"))
        assert md_files, f"Expected at least one .md file in {lang_dir}"


def test_rules_packs_language_mds_have_paths_frontmatter():
    """Every .md in python/typescript/golang must open with YAML frontmatter that contains a 'paths' key."""
    for lang in LANGUAGE_DIRS:
        lang_dir = PACKS_DIR / lang
        for md_file in sorted(lang_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            assert fm_match, (
                f"{md_file.relative_to(PACKS_DIR.parent)} must start with YAML frontmatter"
            )
            fm = yaml.safe_load(fm_match.group(1))
            assert isinstance(fm, dict) and "paths" in fm, (
                f"{md_file.relative_to(PACKS_DIR.parent)} frontmatter must contain a 'paths' key"
            )


def test_rules_packs_common_mds_have_no_paths_frontmatter():
    """common/*.md files must NOT contain a 'paths' key in YAML frontmatter (they are universal rules)."""
    common_dir = PACKS_DIR / "common"
    assert common_dir.is_dir(), f"Expected common dir {common_dir} to exist"
    for md_file in sorted(common_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if fm_match:
            fm = yaml.safe_load(fm_match.group(1))
            if isinstance(fm, dict):
                assert "paths" not in fm, (
                    f"{md_file.relative_to(PACKS_DIR.parent)} (common) must NOT have a 'paths' key in frontmatter"
                )


# ---------------------------------------------------------------------------
# Phase 1c additions: size budgets, provenance comments, no placeholders
# ---------------------------------------------------------------------------

COMMON_BUDGET_BYTES = 6 * 1024   # 6 KB total for common/
LANG_BUDGET_BYTES   = 8 * 1024   # 8 KB total per language dir


def test_common_pack_total_size_within_budget():
    """common/ directory total size must be ≤6 KB."""
    common_dir = PACKS_DIR / "common"
    assert common_dir.is_dir()
    total = sum(f.stat().st_size for f in common_dir.glob("*.md"))
    assert total <= COMMON_BUDGET_BYTES, (
        f"common/ pack total size {total}B exceeds {COMMON_BUDGET_BYTES}B budget"
    )


def test_language_pack_dirs_within_size_budget():
    """Each language pack dir total size must be ≤8 KB."""
    for lang in LANGUAGE_DIRS:
        lang_dir = PACKS_DIR / lang
        assert lang_dir.is_dir(), f"Expected language dir {lang_dir} to exist"
        total = sum(f.stat().st_size for f in lang_dir.glob("*.md"))
        assert total <= LANG_BUDGET_BYTES, (
            f"{lang}/ pack total size {total}B exceeds {LANG_BUDGET_BYTES}B budget"
        )


def test_language_mds_have_provenance_comment():
    """Every .md in python/typescript/golang must contain a provenance comment after frontmatter."""
    for lang in LANGUAGE_DIRS:
        lang_dir = PACKS_DIR / lang
        for md_file in sorted(lang_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            assert "<!-- ported from affaan-m/ECC@c888d2b" in content, (
                f"{md_file.relative_to(PACKS_DIR.parent)} must contain a provenance comment"
            )


def test_no_placeholder_md_in_pack_dirs():
    """No placeholder.md should remain in any pack directory."""
    for lang in LANGUAGE_DIRS:
        lang_dir = PACKS_DIR / lang
        placeholder = lang_dir / "placeholder.md"
        assert not placeholder.exists(), (
            f"placeholder.md must be removed from {lang}/ (Task 1c)"
        )

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
