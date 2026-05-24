"""Plugin generator for orchestrator-based Claude Code integration."""
import json
import shutil
from pathlib import Path
from typing import Optional


COPY_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")


def generate_plugin_manifest(
    target_dir: str,
    project_name: str,
    plugin_version: str = "1.0.0",
    skills_dir: Optional[Path] = None,
    logical_plugin_dir: Optional[str] = None
) -> str:
    """Generate plugin.json for the orchestrator plugin.

    Args:
        target_dir: Directory to generate plugin in (e.g., .claude/plugin-generated)
        project_name: Name of the project (for display)
        plugin_version: Version of the plugin
        skills_dir: Ignored legacy parameter kept for call compatibility
        logical_plugin_dir: Ignored legacy parameter kept for call compatibility

    Returns:
        Path to the generated plugin.json
    """
    plugin_dir = Path(target_dir)
    
    hooks_dir = plugin_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    settings = {
        "name": "orchestrator-plugin",
        "description": f"Auto-generated orchestrator plugin for {project_name}",
        "version": plugin_version,
        "author": {
            "name": "E2G Harness"
        }
    }

    claude_plugin_dir = plugin_dir / ".claude-plugin"
    claude_plugin_dir.mkdir(parents=True, exist_ok=True)
    settings_path = claude_plugin_dir / "plugin.json"
    
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)

    return str(settings_path)


def generate_local_marketplace(
    harness_dir: Path,
    plugin_version: str = "1.0.0"
) -> str:
    """Generate a project-local marketplace manifest for Claude plugin install readiness."""
    marketplace_dir = Path(harness_dir) / ".claude-plugin"
    marketplace_dir.mkdir(parents=True, exist_ok=True)
    marketplace = {
        "name": "local-orchestrator-marketplace",
        "description": "Project-local marketplace for the generated orchestrator plugin",
        "version": plugin_version,
        "owner": {
            "name": "E2G Harness"
        },
        "plugins": [
            {
                "name": "orchestrator-plugin",
                "source": "./plugin-generated",
                "description": "Project-local orchestrator plugin for the generated harness",
                "version": plugin_version,
                "author": {
                    "name": "E2G Harness"
                }
            }
        ]
    }
    marketplace_path = marketplace_dir / "marketplace.json"
    with open(marketplace_path, "w") as f:
        json.dump(marketplace, f, indent=2)
    return str(marketplace_path)


def export_orchestrator_config(orchestrator_path: Path, config_dir: Path, logical_orchestrator_path: Optional[Path] = None) -> str:
    """Export orchestrator configuration from .md to JSON format.

    Args:
        orchestrator_path: Path to orchestrator.md
        config_dir: Directory to export config to
        logical_orchestrator_path: Optional final intended path for the orchestrator file

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
        "source": str(logical_orchestrator_path or orchestrator_path),
        "content": content,
        "generated_at": "auto"
    }

    export_path = config_dir / "orchestrator.json"
    with open(export_path, 'w') as f:
        json.dump(orchestrator_json, f, indent=2)

    return str(export_path)


def export_agents_config(agents_dir: Path, config_dir: Path, logical_agents_dir: Optional[Path] = None) -> str:
    """Export agent definitions from agents/ directory to agents.json.

    Args:
        agents_dir: Path to agents directory
        config_dir: Directory to export config to
        logical_agents_dir: Optional final intended path for the agents directory

    Returns:
        Path to exported agents.json
    """
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)

    agents = {}
    if agents_dir.exists():
        for agent_file in sorted(agents_dir.glob("*.md")):
            agent_name = agent_file.stem
            
            # Use logical path if provided
            if logical_agents_dir:
                agent_path = logical_agents_dir / agent_file.name
            else:
                agent_path = agent_file
                
            with open(agent_file, 'r') as f:
                agents[agent_name] = {
                    "path": str(agent_path),
                    "source": f.read()
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
        for rule_file in sorted(rules_dir.glob("*.md")):
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


def copy_static_plugin_assets(plugin_dir: Path, bp_dir: Path, fallback_bp_dir: Path) -> None:
    """Copy canonical static plugin payload directories and files."""
    for name in ["skills", "scripts", "hooks", "contracts", "state"]:
        source = bp_dir / name
        if not source.exists():
            source = fallback_bp_dir / name

        if source.exists():
            print(f"[HARNESS] Copying {name} from {source}...")
            shutil.copytree(source, plugin_dir / name, dirs_exist_ok=True, ignore=COPY_IGNORE)
        else:
            print(f"[HARNESS] Warning: {name.capitalize()} source {source} not found.")

    pyproject_src = bp_dir / "pyproject.toml"
    if not pyproject_src.exists():
        pyproject_src = fallback_bp_dir / "pyproject.toml"

    if pyproject_src.exists():
        print(f"[HARNESS] Copying pyproject.toml from {pyproject_src}...")
        shutil.copy(pyproject_src, plugin_dir / "pyproject.toml")
    else:
        print(f"[HARNESS] Warning: pyproject.toml source {pyproject_src} not found.")


def copy_runtime_modules(plugin_dir: Path) -> None:
    """Copy the runtime Python modules still used by setup smoke tests."""
    src_dir = plugin_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "__init__.py").write_text("")

    harness_module_dir = Path(__file__).parent
    for core_file in ["dispatcher.py", "database.py", "instrumentation.py", "discovery_engine.py", "renderer.py", "utils.py"]:
        src_path = harness_module_dir / core_file
        if src_path.exists():
            print(f"[HARNESS] Copying {core_file}...")
            shutil.copy(src_path, src_dir / core_file)
        else:
            print(f"[HARNESS] Warning: {core_file} not found at {src_path}")


def remove_obsolete_generated_files(plugin_dir: Path) -> None:
    """Remove legacy generated plugin payloads that are no longer registered."""
    obsolete_files = [
        plugin_dir / "src" / "orchestrator_plugin.py",
        plugin_dir / "src" / "interceptor.py",
        plugin_dir / "src" / "tools.py",
        plugin_dir / "src" / "hook_validator.py",
    ]
    for path in obsolete_files:
        if path.exists():
            path.unlink()

    obsolete_dirs = [
        plugin_dir / "src" / "hooks",
    ]
    for path in obsolete_dirs:
        if path.exists():
            shutil.rmtree(path)


def render_plugin_readme(plugin_dir: Path, bp_dir: Path, fallback_bp_dir: Path, project_name: str) -> str:
    """Render plugin README from the static boilerplate template."""
    template_path = bp_dir / "README.md.template"
    if not template_path.exists():
        template_path = fallback_bp_dir / "README.md.template"

    if template_path.exists():
        readme_content = template_path.read_text().format(project_name=project_name)
    else:
        readme_content = f"""# Orchestrator Plugin

This is the auto-generated Claude Code plugin for {project_name}.

## Local Development and Validation

To manually test and validate this plugin, you can run Claude Code and point it directly to this directory:

```bash
claude --plugin-dir ./.claude/plugin-generated
```
"""

    readme_path = plugin_dir / "README.md"
    readme_path.write_text(readme_content)
    return str(readme_path)


def generate_orchestrator_plugin(
    project_path: str,
    project_name: str,
    plugin_version: str = "1.0.0",
    boilerplate_dir: Optional[str] = None,
    harness_folder: str = ".claude",
    logical_harness_name: Optional[str] = None
) -> str:
    """Generate a complete orchestrator plugin for the project.

    Args:
        project_path: Root path of the project
        project_name: Name of the project
        plugin_version: Version of the plugin
        boilerplate_dir: Optional path to boilerplate directory
        harness_folder: The name of the harness folder (e.g., .claude, .harness_tmp)
        logical_harness_name: The final intended name of the harness folder (e.g. .claude)

    Returns:
        Path to the generated plugin directory
    """
    try:
        project_path = Path(project_path).resolve()
        plugin_dir = project_path / harness_folder / "plugin-generated"
        
        # Calculate logical plugin dir for manifest
        final_harness = logical_harness_name if logical_harness_name else harness_folder
        logical_plugin_dir = project_path / final_harness / "plugin-generated"

        config_dir = plugin_dir / "config"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        config_dir.mkdir(parents=True, exist_ok=True)

        harness_dir = project_path / harness_folder
        logical_harness_dir = project_path / final_harness
        
        # Resolve boilerplate dir
        from harness.utils import get_boilerplate_dir
        bp_dir = Path(boilerplate_dir).resolve() if boilerplate_dir else get_boilerplate_dir()
        fallback_bp_dir = get_boilerplate_dir()

        print(f"[HARNESS] Generating plugin at {plugin_dir}")
        print(f"[HARNESS] Using boilerplate from {bp_dir}")

        # Copy canonical static plugin payload.
        copy_static_plugin_assets(plugin_dir, bp_dir, fallback_bp_dir)
        remove_obsolete_generated_files(plugin_dir)

        # Generate manifest
        print(f"[HARNESS] Generating manifest...")
        generate_plugin_manifest(str(plugin_dir), project_name, plugin_version, logical_plugin_dir=str(logical_plugin_dir))
        generate_local_marketplace(project_path / harness_folder, plugin_version=plugin_version)

        # Export configs
        print(f"[HARNESS] Exporting configs...")
        if harness_dir.exists():
            if (harness_dir / "orchestrator.md").exists():
                logical_orchestrator = logical_harness_dir / "orchestrator.md"
                export_orchestrator_config(harness_dir / "orchestrator.md", config_dir, logical_orchestrator_path=logical_orchestrator)
            if (harness_dir / "rules").exists():
                export_rules_config(harness_dir / "rules", config_dir)

        # Copy boilerplate agents first
        agents_src = bp_dir / "agents"
        if agents_src.exists():
            print(f"[HARNESS] Copying boilerplate agents from {agents_src}...")
            shutil.copytree(agents_src, plugin_dir / "agents", dirs_exist_ok=True, ignore=COPY_IGNORE)
            
        # Copy dynamically generated agents from harness temp dir
        harness_agents = harness_dir / "agents"
        if harness_agents.exists():
            print(f"[HARNESS] Copying dynamically generated agents from {harness_agents}...")
            shutil.copytree(harness_agents, plugin_dir / "agents", dirs_exist_ok=True, ignore=COPY_IGNORE)

        # Generate config if we copied any agents
        if (plugin_dir / "agents").exists():
            # Use logical path for agents.json references
            logical_agents_dir = logical_plugin_dir / "agents"
            export_agents_config(plugin_dir / "agents", config_dir, logical_agents_dir=logical_agents_dir)
        else:
            print(f"[HARNESS] Warning: No agents found to copy.")

        # Export DDD context
        context_path = project_path / "docs" / "domain" / "CONTEXT.md"
        print(f"[HARNESS] Exporting DDD context from {context_path}...")
        export_ddd_context(context_path, config_dir)

        print(f"[HARNESS] Copying runtime modules...")
        copy_runtime_modules(plugin_dir)

        render_plugin_readme(plugin_dir, bp_dir, fallback_bp_dir, project_name)

        print(f"[HARNESS] Plugin generation complete.")
        return str(plugin_dir)
    except Exception as e:
        print(f"[HARNESS] ERROR during plugin generation: {e}")
        import traceback
        traceback.print_exc()
        raise
