"""Tests for dynamic manifest and tiered tools."""
import json
import tempfile
from pathlib import Path
import pytest
from harness.plugin_generator import (
    generate_plugin_manifest,
    generate_plugin_sources,
)

class TestDynamicManifest:
    """Task 4: Phase 4 - Dynamic Manifest & Tiered Tools tests."""

    def test_generate_plugin_manifest_with_skills_tiered_tools(self):
        """Test that plugin manifest includes tiered tools for skills."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "test-project"
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir()
            
            # Create some mock skills
            skills = ["harnesstdd", "brainstorming", "systematic-debugging"]
            for skill in skills:
                (skills_dir / skill).mkdir()
                (skills_dir / skill / "SKILL.md").write_text(f"# {skill}")

            target_dir = Path(tmpdir) / "plugin"
            manifest_path = generate_plugin_manifest(
                str(target_dir), 
                project_name, 
                skills_dir=skills_dir
            )

            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            # Check tiered tools
            tool_names = [t["name"] for t in manifest["tools"]]
            for skill in skills:
                tool_name = f"skill_{skill.replace('-', '_')}"
                assert tool_name in tool_names
                
                # Verify entry point
                tool = next(t for t in manifest["tools"] if t["name"] == tool_name)
                assert tool["entry_point"] == f"src/tools.py:invoke_specific_{tool_name}"

            # Verify generic tools still exist
            assert "Skill" in tool_names
            assert "Task" in tool_names

    def test_generate_plugin_manifest_caps_at_10_skills(self):
        """Test that only top 10 skills are registered as first-class tools."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir()
            
            for i in range(15):
                (skills_dir / f"skill-{i:02d}").mkdir()
                (skills_dir / f"skill-{i:02d}" / "SKILL.md").write_text(f"# Skill {i}")

            target_dir = Path(tmpdir) / "plugin"
            manifest_path = generate_plugin_manifest(
                str(target_dir), 
                "test-project", 
                skills_dir=skills_dir
            )

            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            skill_tools = [t for t in manifest["tools"] if t["name"].startswith("skill_")]
            assert len(skill_tools) == 10

    def test_generate_plugin_manifest_includes_windows_compatible_hooks(self):
        """Test that manifest includes correct hook registrations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / "plugin"
            manifest_path = generate_plugin_manifest(str(target_dir), "test-project")

            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            hooks = manifest["hooks"]
            
            # Check UserPromptSubmit
            assert "UserPromptSubmit" in hooks
            assert hooks["UserPromptSubmit"][0]["type"] == "command"
            assert "python -m src.hooks.prompt_interceptor" in hooks["UserPromptSubmit"][0]["command"]

            # Check PreToolUse
            assert "PreToolUse" in hooks
            assert hooks["PreToolUse"][0]["type"] == "command"
            assert "python -m src.hooks.pre_tool_guard" in hooks["PreToolUse"][0]["command"]

            # Check Stop
            assert "Stop" in hooks
            assert hooks["Stop"][0]["type"] == "command"
            assert "python -m src.hooks.stop_monitor" in hooks["Stop"][0]["command"]

    def test_generate_plugin_sources_creates_dynamic_skill_handlers(self):
        """Test that tools.py contains dynamic handlers for tiered skills."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir()
            (skills_dir / "harnesstdd").mkdir()
            (skills_dir / "harnesstdd" / "SKILL.md").write_text("# Harness TDD")
            
            src_dir = Path(tmpdir) / "src"
            
            # We need to pass skills_dir to generate_plugin_sources or rely on it being there
            # Actually, generate_plugin_sources might need updating to accept skills_dir
            generate_plugin_sources(src_dir, skills_dir=skills_dir)
            
            tools_content = (src_dir / "tools.py").read_text()
            assert "def invoke_specific_skill_harnesstdd" in tools_content
            assert 'return invoke_skill("harnesstdd")' in tools_content
