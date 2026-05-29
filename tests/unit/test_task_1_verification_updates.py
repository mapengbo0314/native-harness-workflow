
import os
from pathlib import Path

def test_verifier_template_has_metadata_requirement():
    repo_root = Path(__file__).parent.parent.parent
    verifier_path = repo_root / "src" / "harness" / "templates" / "boilerplate" / "agents" / "verifier.md"
    
    assert verifier_path.exists()
    content = verifier_path.read_text()
    
    assert "SUPERPOWER MANDATE:" in content
    assert "verification-before-completion" in content

def test_verification_skill_has_metadata_parsing_step():
    repo_root = Path(__file__).parent.parent.parent
    skill_path = repo_root / "src" / "harness" / "templates" / "boilerplate" / "skills" / "verification-before-completion" / "SKILL.md"
    
    assert skill_path.exists()
    content = skill_path.read_text()
    
    assert "Extract Metadata" in content or "metadata" in content.lower()
    assert "<QA_METADATA>" in content
