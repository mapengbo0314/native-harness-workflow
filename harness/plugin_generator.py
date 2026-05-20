"""Plugin generator for orchestrator-based Claude Code integration."""
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional


def generate_plugin_manifest(
    target_dir: str,
    project_name: str,
    plugin_version: str = "1.0.0"
) -> str:
    """Generate plugin.json manifest for the orchestrator plugin.

    Args:
        target_dir: Directory to generate plugin in (e.g., .claude/plugin-generated)
        project_name: Name of the project (for display)
        plugin_version: Version of the plugin

    Returns:
        Path to the generated plugin.json
    """
    plugin_dir = Path(target_dir)
    plugin_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": "orchestrator-plugin",
        "description": f"Auto-generated orchestrator plugin for {project_name}",
        "version": plugin_version,
        "author": "Harness Plugin Generator",
        "entry_point": "src/orchestrator_plugin.py",
        "requirements": [
            "pydantic>=2.0",
            "typing_extensions"
        ],
        "hooks": {
            "agent_dispatch": "src/interceptor.py:intercept_agent_dispatch"
        }
    }

    manifest_path = plugin_dir / "plugin.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    return str(manifest_path)


def export_orchestrator_config(orchestrator_path: Path, config_dir: Path) -> str:
    """Export orchestrator configuration from .md to JSON format.

    Args:
        orchestrator_path: Path to orchestrator.md
        config_dir: Directory to export config to

    Returns:
        Path to exported orchestrator.json
    """
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)

    # Read orchestrator.md
    with open(orchestrator_path, 'r') as f:
        content = f.read()

    # Create a basic JSON with metadata
    orchestrator_json = {
        "source": str(orchestrator_path),
        "content": content,
        "generated_at": "auto"
    }

    export_path = config_dir / "orchestrator.json"
    with open(export_path, 'w') as f:
        json.dump(orchestrator_json, f, indent=2)

    return str(export_path)


def export_agents_config(agents_dir: Path, config_dir: Path) -> str:
    """Export agent definitions from agents/ directory to agents.json.

    Args:
        agents_dir: Path to agents directory
        config_dir: Directory to export config to

    Returns:
        Path to exported agents.json
    """
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)

    agents = {}
    if agents_dir.exists():
        for agent_file in agents_dir.glob("*.md"):
            agent_name = agent_file.stem
            with open(agent_file, 'r') as f:
                agents[agent_name] = {
                    "path": str(agent_file),
                    "source": f.read()[:200]  # First 200 chars
                }

    agents_json = {
        "agents": agents,
        "count": len(agents)
    }

    export_path = config_dir / "agents.json"
    with open(export_path, 'w') as f:
        json.dump(agents_json, f, indent=2)

    return str(export_path)


def export_ddd_context(context_path: Path, config_dir: Path) -> str:
    """Export DDD context from CONTEXT.md to ddd-context.json.

    Args:
        context_path: Path to docs/domain/CONTEXT.md
        config_dir: Directory to export config to

    Returns:
        Path to exported ddd-context.json
    """
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)

    ddd_context = {
        "purpose": "",
        "ubiquitous_language": {},
        "strict_invariants": []
    }

    if context_path.exists():
        with open(context_path, 'r') as f:
            content = f.read()
        ddd_context["source"] = content

    export_path = config_dir / "ddd-context.json"
    with open(export_path, 'w') as f:
        json.dump(ddd_context, f, indent=2)

    return str(export_path)


def export_rules_config(rules_dir: Path, config_dir: Path) -> str:
    """Export project mandates/rules to rules.json.

    Args:
        rules_dir: Path to rules/ directory
        config_dir: Directory to export config to

    Returns:
        Path to exported rules.json
    """
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)

    rules = {}
    if rules_dir.exists():
        for rule_file in rules_dir.glob("*.md"):
            rule_name = rule_file.stem
            with open(rule_file, 'r') as f:
                rules[rule_name] = f.read()

    rules_json = {
        "rules": rules,
        "count": len(rules)
    }

    export_path = config_dir / "rules.json"
    with open(export_path, 'w') as f:
        json.dump(rules_json, f, indent=2)

    return str(export_path)


def generate_orchestrator_plugin(
    project_path: str,
    project_name: str,
    plugin_version: str = "1.0.0"
) -> str:
    """Generate a complete orchestrator plugin for the project.

    Args:
        project_path: Root path of the project
        project_name: Name of the project
        plugin_version: Version of the plugin

    Returns:
        Path to the generated plugin directory
    """
    project_path = Path(project_path)
    plugin_dir = project_path / ".claude" / "plugin-generated"

    # Create directory structure
    src_dir = plugin_dir / "src"
    config_dir = plugin_dir / "config"
    src_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    # Generate manifest
    generate_plugin_manifest(str(plugin_dir), project_name, plugin_version)

    # Export configs
    harness_dir = project_path / ".claude"
    if harness_dir.exists():
        if (harness_dir / "orchestrator.md").exists():
            export_orchestrator_config(harness_dir / "orchestrator.md", config_dir)
        if (harness_dir / "agents").exists():
            export_agents_config(harness_dir / "agents", config_dir)
        if (harness_dir / "rules").exists():
            export_rules_config(harness_dir / "rules", config_dir)

    # Export DDD context
    context_path = project_path / "docs" / "domain" / "CONTEXT.md"
    export_ddd_context(context_path, config_dir)

    # Generate plugin source files
    generate_plugin_sources(src_dir)

    # Generate pyproject.toml
    generate_pyproject(plugin_dir)

    return str(plugin_dir)


def generate_plugin_sources(src_dir: Path) -> None:
    """Generate plugin source files: orchestrator_plugin.py, dispatcher.py, interceptor.py."""
    src_dir = Path(src_dir)
    src_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py
    (src_dir / "__init__.py").write_text("")

    # Stub files - will be replaced with full implementation in tasks 8-9
    (src_dir / "orchestrator_plugin.py").write_text(
        '"""Plugin entry point - stub for implementation"""\n'
    )
    (src_dir / "dispatcher.py").write_text(
        '"""Dispatcher logic - stub for implementation"""\n'
    )
    (src_dir / "interceptor.py").write_text(
        '"""Hook interception - stub for implementation"""\n'
    )


def generate_pyproject(plugin_dir: Path) -> str:
    """Generate pyproject.toml for the plugin."""
    pyproject_content = """[project]
name = "orchestrator-plugin"
version = "1.0.0"
description = "Auto-generated orchestrator plugin"
requires-python = ">=3.8"

dependencies = [
    "pydantic>=2.0",
    "typing_extensions>=4.0"
]

[tool.poetry]
packages = [
    { include = "src" }
]
"""

    pyproject_path = plugin_dir / "pyproject.toml"
    with open(pyproject_path, 'w') as f:
        f.write(pyproject_content)

    return str(pyproject_path)
