"""Tests for orchestrator plugin generator."""
import json
import tempfile
from pathlib import Path

import pytest

from harness.plugin_generator import (
    generate_orchestrator_plugin,
    generate_plugin_manifest,
    export_orchestrator_config,
    export_agents_config,
    export_rules_config,
    export_ddd_context,
    generate_plugin_sources,
    generate_pyproject,
)
from harness.dispatcher import OrchestratorDispatcher


class TestDeepCopyMigration:
    """Phase 1: Deep Copy Migration tests."""

    def test_generate_orchestrator_plugin_deep_copies_agents_and_skills(self):
        """Test that agents and skills are recursively copied to the plugin directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            
            # Create boilerplate-agent structure
            boilerplate_dir = project_path / "boilerplate-agent"
            boilerplate_dir.mkdir()
            
            agents_src = boilerplate_dir / "agents"
            agents_src.mkdir()
            (agents_src / "tester.md").write_text("# Tester Agent")
            
            skills_src = boilerplate_dir / "skills"
            skills_src.mkdir()
            skill_dir = skills_src / "test-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Test Skill")

            skills_scripts_dir = skill_dir / "scripts"
            skills_scripts_dir.mkdir()
            (skills_scripts_dir / "helper.sh").write_text("#!/bin/bash\necho helper")

            # Create boilerplate-agent/scripts
            root_scripts_dir = boilerplate_dir / "scripts"
            root_scripts_dir.mkdir()
            (root_scripts_dir / "gatekeeper.py").write_text("# Gatekeeper")

            # Create minimal .claude/orchestrator.md to avoid errors if needed
            harness_dir = project_path / ".claude"
            harness_dir.mkdir()
            (harness_dir / "orchestrator.md").write_text("# Orchestrator")

            # Call generate function
            plugin_dir = generate_orchestrator_plugin(
                project_path=str(project_path),
                project_name="test-project"
            )

            plugin_path = Path(plugin_dir)

            # Verify agents were copied
            agents_dest = plugin_path / "agents"
            assert agents_dest.exists()
            assert (agents_dest / "tester.md").exists()

            # Verify skills were copied recursively
            skills_dest = plugin_path / "skills"
            assert skills_dest.exists()
            assert (skills_dest / "test-skill" / "SKILL.md").exists()
            assert (skills_dest / "test-skill" / "scripts" / "helper.sh").exists()
            assert (skills_dest / "test-skill" / "scripts" / "helper.sh").read_text() == "#!/bin/bash\necho helper"

            # Verify scripts were copied
            scripts_dest = plugin_path / "scripts"
            assert scripts_dest.exists()
            assert (scripts_dest / "gatekeeper.py").exists()
            assert (scripts_dest / "gatekeeper.py").read_text() == "# Gatekeeper"

class TestTask1PluginManifest:
    """Task 1: Plugin manifest generation."""

    def test_generate_plugin_manifest_creates_valid_json(self):
        """Test that plugin manifest is generated with correct structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "test-project"
            manifest_path = generate_plugin_manifest(tmpdir, project_name)

            assert Path(manifest_path).exists()
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            assert manifest['name'] == 'orchestrator-plugin'
            assert manifest['description'] == 'Auto-generated orchestrator plugin for test-project'
            assert manifest['version'] == '1.0.0'
            assert 'entry_point' in manifest
            assert 'hooks' in manifest


class TestTask2ConfigExport:
    """Task 2: Config export functions."""

    def test_export_orchestrator_config_copies_orchestrator_md(self):
        """Test that orchestrator.json is exported from orchestrator.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator_path = Path(tmpdir) / "orchestrator.md"
            orchestrator_path.write_text("# Orchestrator\n\nRouting rules...")

            config_dir = Path(tmpdir) / "config"
            result = export_orchestrator_config(orchestrator_path, config_dir)

            assert (config_dir / "orchestrator.json").exists()
            assert result == str(config_dir / "orchestrator.json")

    def test_export_agents_config_scans_agent_files(self):
        """Test that agents.json is exported from agents directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir) / "agents"
            agents_dir.mkdir()
            full_planner = "# Planner Agent\n" + ("Full instructions.\n" * 30)
            (agents_dir / "planner.md").write_text(full_planner)
            (agents_dir / "reviewer.md").write_text("# Reviewer Agent")

            config_dir = Path(tmpdir) / "config"
            result = export_agents_config(agents_dir, config_dir)

            assert (config_dir / "agents.json").exists()
            with open(config_dir / "agents.json", 'r') as f:
                data = json.load(f)
                assert "planner" in data["agents"]
                assert "reviewer" in data["agents"]
                assert data["agents"]["planner"]["source"] == full_planner

    def test_export_rules_config_scans_rule_files(self):
        """Test that rules.json is exported from rules directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_dir = Path(tmpdir) / "rules"
            rules_dir.mkdir()
            (rules_dir / "core_mandates.md").write_text("# Core Mandates")
            (rules_dir / "security.md").write_text("# Security")

            config_dir = Path(tmpdir) / "config"
            result = export_rules_config(rules_dir, config_dir)

            assert (config_dir / "rules.json").exists()
            with open(config_dir / "rules.json", 'r') as f:
                data = json.load(f)
                assert "core_mandates" in data["rules"]
                assert "security" in data["rules"]

    def test_export_ddd_context_handles_missing_file(self):
        """Test that ddd-context.json handles missing CONTEXT.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            context_path = Path(tmpdir) / "CONTEXT.md"  # Does not exist

            result = export_ddd_context(context_path, config_dir)

            assert (config_dir / "ddd-context.json").exists()


class TestTask3PluginGeneration:
    """Task 3: Main generate_orchestrator_plugin() function."""

    def test_generate_orchestrator_plugin_creates_complete_structure(self):
        """Test that generate_orchestrator_plugin creates all required files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal harness structure
            harness_dir = Path(tmpdir) / ".claude"
            harness_dir.mkdir()
            (harness_dir / "orchestrator.md").write_text("# Orchestrator")
            (harness_dir / "agents").mkdir()
            (harness_dir / "agents" / "planner.md").write_text("# Planner Agent")
            (harness_dir / "rules").mkdir()
            (harness_dir / "rules" / "core_mandates.md").write_text("# Core Mandates")

            docs_dir = Path(tmpdir) / "docs" / "domain"
            docs_dir.mkdir(parents=True)
            (docs_dir / "CONTEXT.md").write_text("# Context")

            # Call generate function
            plugin_dir = generate_orchestrator_plugin(
                project_path=tmpdir,
                project_name="test-project"
            )

            # Verify structure
            plugin_path = Path(plugin_dir)
            assert (plugin_path / ".claude-plugin" / "plugin.json").exists()
            assert (plugin_path / "src" / "orchestrator_plugin.py").exists()
            assert (plugin_path / "src" / "dispatcher.py").exists()
            assert (plugin_path / "src" / "interceptor.py").exists()
            assert (plugin_path / "config" / "orchestrator.json").exists()
            assert (plugin_path / "config" / "rules.json").exists()
            assert (plugin_path / "config" / "ddd-context.json").exists()
            assert (plugin_path / "config" / "agents.json").exists()
            assert (plugin_path / "agents").exists()
            assert (plugin_path / "pyproject.toml").exists()


class TestTask7Dispatcher:
    """Task 7: Dispatcher with orchestrator routing."""

    def test_dispatcher_routes_agent_request(self):
        """Test that dispatcher routes agent requests through orchestrator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir(parents=True)

            # Create mock config files
            agents_config = {"agents": {"planner": {}}, "count": 1}
            rules_config = {"rules": {}, "count": 0}
            orch_config = {"source": "mock", "content": "# Mock"}

            with open(config_dir / "agents.json", 'w') as f:
                json.dump(agents_config, f)
            with open(config_dir / "rules.json", 'w') as f:
                json.dump(rules_config, f)
            with open(config_dir / "orchestrator.json", 'w') as f:
                json.dump(orch_config, f)

            dispatcher = OrchestratorDispatcher(str(config_dir))
            result = dispatcher.dispatch_agent("planner", {})

            assert result["agent"] == "planner"
            assert result["routed"] is True
            assert result["orchestrator_applied"] is True

    def test_dispatcher_validates_agent_exists(self):
        """Test that dispatcher validates agent exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir(parents=True)

            agents_config = {"agents": {}, "count": 0}
            with open(config_dir / "agents.json", 'w') as f:
                json.dump(agents_config, f)

            dispatcher = OrchestratorDispatcher(str(config_dir))

            with pytest.raises(ValueError, match="not found in configuration"):
                dispatcher.dispatch_agent("nonexistent-agent", {})


class TestTask8PluginSources:
    """Task 8: Plugin source file generation."""

    def test_generate_plugin_sources_creates_all_files(self):
        """Test that plugin sources are generated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"

            generate_plugin_sources(src_dir)

            assert (src_dir / "__init__.py").exists()
            assert (src_dir / "orchestrator_plugin.py").exists()
            assert (src_dir / "dispatcher.py").exists()
            assert (src_dir / "interceptor.py").exists()


class TestTask10Pyproject:
    """Task 10: pyproject.toml generation."""

    def test_generate_pyproject_creates_toml(self):
        """Test that pyproject.toml is generated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)

            result = generate_pyproject(plugin_dir)

            assert Path(result).exists()
            with open(result, 'r') as f:
                content = f.read()
                assert "[project]" in content
                assert "orchestrator-plugin" in content
                assert "pydantic" in content


class TestIntegration:
    """Integration tests for complete plugin generation flow."""

    def test_complete_plugin_generation_flow(self):
        """Integration test: complete plugin generation workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup project structure
            harness_dir = Path(tmpdir) / ".claude"
            harness_dir.mkdir()
            (harness_dir / "orchestrator.md").write_text(
                "# Main Orchestrator\nKey rules and configurations."
            )

            agents_dir = harness_dir / "agents"
            agents_dir.mkdir()
            (agents_dir / "planner.md").write_text("# Planner Agent")
            (agents_dir / "reviewer.md").write_text("# Reviewer Agent")
            (agents_dir / "implementer.md").write_text("# Implementer Agent")

            rules_dir = harness_dir / "rules"
            rules_dir.mkdir()
            (rules_dir / "base_mandate.md").write_text("# Base Mandate")
            (rules_dir / "coding_mandate.md").write_text("# Coding Mandate")

            docs_dir = Path(tmpdir) / "docs" / "domain"
            docs_dir.mkdir(parents=True)
            (docs_dir / "CONTEXT.md").write_text("# Domain Context")

            # Generate plugin
            plugin_dir = generate_orchestrator_plugin(
                tmpdir,
                "integration-test-project",
                "1.5.0"
            )

            plugin_path = Path(plugin_dir)

            # Verify all expected files exist
            assert (plugin_path / ".claude-plugin" / "plugin.json").exists()
            assert (plugin_path / "pyproject.toml").exists()
            assert (plugin_path / "src" / "__init__.py").exists()
            assert (plugin_path / "src" / "orchestrator_plugin.py").exists()
            assert (plugin_path / "src" / "dispatcher.py").exists()
            assert (plugin_path / "src" / "interceptor.py").exists()
            assert (plugin_path / "config" / "orchestrator.json").exists()
            assert (plugin_path / "agents").exists()
            assert (plugin_path / "config" / "rules.json").exists()
            assert (plugin_path / "config" / "ddd-context.json").exists()

            # Verify manifest content
            with open(plugin_path / ".claude-plugin" / "plugin.json") as f:
                manifest = json.load(f)
            assert manifest["version"] == "1.5.0"

            # Verify agents were deep copied
            agents_copied = list((plugin_path / "agents").glob("*.md"))
            assert len(agents_copied) == 3

            # Verify rule config
            with open(plugin_path / "config" / "rules.json") as f:
                rule_config = json.load(f)
            assert len(rule_config["rules"]) == 2

    def test_plugin_integration_with_dispatcher(self):
        """Integration test: plugin generation + dispatcher routing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Generate plugin
            harness_dir = Path(tmpdir) / ".claude"
            harness_dir.mkdir()
            (harness_dir / "orchestrator.md").write_text("# Orchestrator")
            agents_dir = harness_dir / "agents"
            agents_dir.mkdir()
            (agents_dir / "planner.md").write_text("# Planner")
            (harness_dir / "rules").mkdir()

            plugin_dir = generate_orchestrator_plugin(tmpdir, "test-project")
            config_dir = Path(plugin_dir) / "config"

            # Use dispatcher with generated config
            dispatcher = OrchestratorDispatcher(str(config_dir))
            result = dispatcher.dispatch_agent("planner", {"key": "value"})

            assert result["agent"] == "planner"
            assert result["routed"] is True
            assert result["context"]["key"] == "value"

class TestPhase3Hooks:
    """Task 3: Phase 3 - Standalone Hooks Execution tests."""

    def test_generate_plugin_sources_creates_hooks_directory_and_scripts(self):
        """Test that generate_plugin_sources creates src/hooks/ and the three hook scripts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()

            generate_plugin_sources(src_dir)

            hooks_dir = src_dir / "hooks"
            assert hooks_dir.exists()
            assert hooks_dir.is_dir()

            expected_hooks = [
                "prompt_interceptor.py",
                "pre_tool_guard.py",
                "post_tool_monitor.py",
                "precompact_monitor.py",
                "stop_monitor.py",
            ]
            for hook in expected_hooks:
                hook_path = hooks_dir / hook
                assert hook_path.exists(), f"{hook} should exist"
                
                content = hook_path.read_text()
                
                # Check import resolution header
                assert "import sys, os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))" in content
                
                # Check logging logic
                assert "harness.log" in content
                assert "os.getpid()" in content
                assert "datetime" in content

            # Check XML sanitization in prompt_interceptor.py
            interceptor_content = (hooks_dir / "prompt_interceptor.py").read_text()
            assert "xml.sax.saxutils.escape" in interceptor_content
            assert "<matrix_route branch=" in interceptor_content
            assert "classify_intent" in interceptor_content

            pre_tool_content = (hooks_dir / "pre_tool_guard.py").read_text()
            assert "Orchestrators cannot write code" in pre_tool_content
            assert "TDD VIOLATION" in pre_tool_content

            post_tool_content = (hooks_dir / "post_tool_monitor.py").read_text()
            assert "last_failing_test" in post_tool_content
            assert "last_codegraph_use_at" in post_tool_content
