import argparse
import importlib.util
import json
import shlex
import sys
import getpass
import os
import subprocess
import shutil
import time
import uuid
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from langfuse import observe
from harness.runtime.langfuse_compat import langfuse_context

load_dotenv()


class HarnessSetupError(RuntimeError):
    """Raised when mandatory one-step harness setup cannot be completed."""


def _platform_name(platform_choice: str) -> str:
    return {
        "1": "gemini",
        "2": "claude",
        "3": "cursor",
        "4": "agents",
        "5": "codex",
    }.get(platform_choice, platform_choice).lower()


def _build_mcp_config(mcps_to_install: list[dict]) -> dict:
    mcp_servers = {
        "codegraph": {
            "command": "npx",
            "args": ["-y", "@colbymchenry/codegraph", "serve", "--mcp"],
        }
    }

    for mcp in mcps_to_install or []:
        command = mcp.get("command", "")
        try:
            parts = shlex.split(command)
        except ValueError as exc:
            raise HarnessSetupError(f"Invalid command string for MCP {mcp.get('name')}: {exc}") from exc
        if parts:
            mcp_servers[mcp["name"]] = {
                "command": parts[0],
                "args": parts[1:],
            }

    return {"mcpServers": mcp_servers}


from harness.adapters import get_adapter

def _validate_claude_plugin(project_path: Path, plugin_dir: Path) -> None:
    required = [
        plugin_dir / ".claude-plugin" / "plugin.json",
        plugin_dir / "hooks" / "hooks.json",
        plugin_dir / "hooks" / "prompt_classifier.py",
        plugin_dir / "src" / "dispatcher.py",
        plugin_dir / "agents",
        plugin_dir / "skills",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise HarnessSetupError("Generated plugin payload is incomplete:\n" + "\n".join(f"  - {path}" for path in missing))

    if (plugin_dir / "src" / "hooks").exists():
        raise HarnessSetupError("Legacy plugin src/hooks payload must not be generated.")

    config_text = "\n".join(path.read_text(encoding="utf-8") for path in plugin_dir.glob("*.json"))
    if ".harness_tmp" in config_text:
        raise HarnessSetupError("Generated plugin config contains staging path .harness_tmp.")

    dispatcher_path = plugin_dir / "src" / "dispatcher.py"
    spec = importlib.util.spec_from_file_location("harness_generated_plugin_dispatcher", dispatcher_path)
    if spec is None or spec.loader is None:
        raise HarnessSetupError(f"Could not load generated dispatcher at {dispatcher_path}")
    dispatcher_module = importlib.util.module_from_spec(spec)
    src_dir = str(plugin_dir / "src")
    sys.path.insert(0, src_dir)
    try:
        spec.loader.exec_module(dispatcher_module)
    finally:
        sys.path.remove(src_dir)

    hooks_config = json.loads((plugin_dir / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    for groups in hooks_config.get("hooks", {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                command = hook.get("command", "")
                resolved = command.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_dir))
                try:
                    parts = shlex.split(resolved)
                except ValueError as exc:
                    raise HarnessSetupError(f"Invalid hook command string: {exc}") from exc
                script = None
                for part in parts:
                    if part.endswith((".py", ".sh", ".js")):
                        script = Path(part)
                        break
                
                if (not script or not script.exists()) and len(parts) > 0 and Path(parts[0]).exists():
                    script = Path(parts[0])
                if not script or not script.exists():
                    raise HarnessSetupError(f"Hook command points at missing script: {command}")

    claude = shutil.which("claude")
    if claude:
        for target in [plugin_dir, project_path / ".claude"]:
            result = subprocess.run(
                [claude, "plugin", "validate", str(target)],
                capture_output=True, 
                text=True,
                env=os.environ.copy()
            )
            if result.returncode != 0:
                raise HarnessSetupError(result.stdout + result.stderr)

    print("[HARNESS] Claude plugin payload validated.")


def run_embedded_setup(
    project_path: Path,
    harness_dir: Path,
    platform_choice: str,
    plugin_dir: Optional[Path],
) -> None:
    print("\n[HARNESS] Running embedded setup...")
    if sys.version_info < (3, 8):
        raise HarnessSetupError("Python 3.8+ is required.")

    adapter = get_adapter(_platform_name(platform_choice))
    adapter.configure_cli(project_path)
    
    if plugin_dir and plugin_dir.exists():
        _validate_claude_plugin(project_path, plugin_dir)

    print("[HARNESS] Embedded setup complete.")

def parse_args():
    parser = argparse.ArgumentParser(description="Initialize a new Harness agent workspace.")
    parser.add_argument("command", choices=["init"], help="Command to run")
    parser.add_argument("--project-path", required=True, help="Path to the repository")
    parser.add_argument("--bundle", help="Path to an existing CodeGraph bundle (.codegraph directory)")
    return parser.parse_args()


@observe()
def main():
    trace_id = os.environ.get("LANGFUSE_TRACE_ID")
    if not trace_id:
        trace_id = str(uuid.uuid4())
        os.environ["LANGFUSE_TRACE_ID"] = trace_id
        
    session_id = os.environ.get("LANGFUSE_SESSION_ID")
    if not session_id:
        session_id = str(uuid.uuid4())
        os.environ["LANGFUSE_SESSION_ID"] = session_id
        
    tags = []
    if os.environ.get("HARNESS_EVAL_MODE") == "1":
        env_tags = os.environ.get("LANGFUSE_TAGS")
        tags = env_tags.split(",") if env_tags else ["integration-test"]
        
    langfuse_context.update_current_trace(session_id=session_id, tags=tags)

    args = parse_args()

    if not shutil.which("npx"):
        print("\nError: 'npx' command not found. Node.js is required to use CodeGraph.")
        langfuse_context.flush()
        sys.exit(1)
        
    print("Pre-flight checks passed.")
    
    # --- CodeGraph Onboarding & Initialization ---
    default_codegraph_dir = os.path.join(args.project_path, ".codegraph")
    codegraph_dir = args.bundle if args.bundle else default_codegraph_dir
    codegraph_db_path = os.path.join(codegraph_dir, "codegraph.db")
    
    if not os.path.exists(codegraph_db_path):
        # If user specified a bundle path that isn't the project default and it's missing, that's a hard error
        if args.bundle and os.path.abspath(args.bundle) != os.path.abspath(default_codegraph_dir):
            print(f"\nError: Specified CodeGraph bundle not found at {codegraph_db_path}")
            langfuse_context.flush()
            sys.exit(1)
            
        print(f"\nCodeGraph database not found. Building now in project root...")
        try:
            # Force non-interactive npm to prevent hidden prompts
            env = os.environ.copy()
            env["npm_config_yes"] = "true"
            env["CODEGRAPH_DEBUG"] = "1"
            
            subprocess.run(
                ["npx", "--yes", "@colbymchenry/codegraph", "init", "--index"],
                cwd=args.project_path,
                env=env,
                check=True
            )
            # After building, ensure we use the newly created default dir
            codegraph_dir = default_codegraph_dir
            codegraph_db_path = os.path.join(codegraph_dir, "codegraph.db")
        except subprocess.CalledProcessError as e:
            print(f"\nWarning: Failed to build CodeGraph: {e}")
            # Continuing without hard crash as per fallback behavior

    print("Stage 1: Resolving bundled boilerplate...")
    boilerplate_dir = Path(__file__).parent.parent / "templates" / "boilerplate"
    
    if not os.path.exists(boilerplate_dir):
        print(f"\nError: Bundled boilerplate not found at {boilerplate_dir}")
        langfuse_context.flush()
        sys.exit(1)
        
    selected_agents = []

    print("\n=== Platform Selection ===")
    print("1. Gemini CLI")
    print("2. Claude Code")
    print("3. Cursor")
    print("4. Generic / Custom")
    print("5. Codex")
    
    if os.environ.get("HARNESS_HEADLESS") == "1":
        platform_choice = os.environ.get("HARNESS_PLATFORM", "1")
        print(f"Headless mode: Defaulting to platform choice ({platform_choice}).")
    else:
        platform_choice = input("Select target platform [1-5]: ").strip()
        if not platform_choice:
            platform_choice = "1"
    
    if platform_choice == "1":
        harness_folder = ".gemini"
    elif platform_choice == "2":
        harness_folder = ".claude"
    elif platform_choice == "3":
        harness_folder = ".cursor"
    elif platform_choice == "5":
        harness_folder = ".codex"
    else:
        harness_folder = ".agents"

    # Normalize project_path to avoid nesting if the user points directly to the harness folder
    # We check against ALL common harness folder names to be safe
    possible_harness_folders = [".gemini", ".claude", ".cursor", ".codex", ".agents"]
    abs_project_path = os.path.abspath(args.project_path)
    path_parts = Path(abs_project_path).parts
    if path_parts and path_parts[-1] in possible_harness_folders:
        print(f"\nNotice: You pointed to a harness folder '{path_parts[-1]}'. Backtracking to project root: {os.path.dirname(abs_project_path)}")
        args.project_path = os.path.dirname(abs_project_path)

    # --- Atomic Swap Setup ---
    import time
    target_harness_dir = Path(args.project_path) / harness_folder
    temp_harness_dir = Path(args.project_path) / ".harness_tmp"
    
    if temp_harness_dir.exists():
        shutil.rmtree(temp_harness_dir)
    temp_harness_dir.mkdir(parents=True)

    from harness.init.minting_engine import (
        mint_workspace
    )

    try:
        # We pass the bundled boilerplate_dir and target the temp directory
        mint_workspace(
            str(temp_harness_dir), 
            selected_agents, 
            args.project_path, 
            platform_choice, 
            boilerplate_dir=str(boilerplate_dir), 
            logical_harness_name=harness_folder
        )

        adapter = get_adapter(_platform_name(platform_choice))

        # Copy runtime modules baked for the selected platform only
        from harness.init.minting_engine import copy_runtime_modules
        copy_runtime_modules(temp_harness_dir, platform_id=_platform_name(platform_choice))

        # Provision core infrastructure for all platforms
        adapter.generate_core_infrastructure(Path(args.project_path))

        # --- Plugin Generation (targeting temp) ---
        from harness.init.plugin_generator import generate_orchestrator_plugin
        
        plugin_dir = None
        # Only Claude generates the distinct orchestrator plugin artifact
        if adapter.get_platform_name() == "claude":
            try:
                print(f"\n[{'='*60}]\n[HARNESS] Generating orchestrator plugin...")
                plugin_dir = generate_orchestrator_plugin(
                    project_path=str(args.project_path),
                    project_name=os.path.basename(args.project_path),
                    boilerplate_dir=boilerplate_dir,
                    harness_folder=".harness_tmp",
                    logical_harness_name=harness_folder,
                )
                
            except Exception as e:
                print(f"\n[HARNESS] ❌ ERROR: Failed to generate orchestrator plugin: {e}")
                import traceback
                traceback.print_exc()
                langfuse_context.flush()
                sys.exit(1)
        
        # --- Handle Root Staging ---
        root_staging_dir = temp_harness_dir / "root_staging"
        if root_staging_dir.exists():
            from harness.init.minting_engine import merge_markdown, merge_structured, handle_code_conflicts
            print(f"\n[HARNESS] Found root staging files. Merging into project root...")
            for root, _, files in os.walk(root_staging_dir):
                for file in files:
                    staged_pointer = Path(root) / file
                    rel_path = staged_pointer.relative_to(root_staging_dir)
                    real_root_file = Path(args.project_path) / rel_path
                    
                    if real_root_file.exists():
                        # Merge existing with staged
                        try:
                            with open(real_root_file, 'r', encoding='utf-8') as f:
                                old_content = f.read()
                            with open(staged_pointer, 'r', encoding='utf-8') as f:
                                new_content = f.read()
                            
                            if file.endswith('.md'):
                                merged = merge_markdown(old_content, new_content)
                            elif file.endswith(('.json', '.yaml', '.yml')):
                                fmt = 'json' if file.endswith('.json') else 'yaml'
                                merged = merge_structured(old_content, new_content, format=fmt)
                            else:
                                # Prompt user for conflict resolution on other files
                                merged = handle_code_conflicts(old_content, new_content, str(rel_path))
                                
                            with open(real_root_file, 'w', encoding='utf-8') as f:
                                f.write(merged)
                            print(f"[HARNESS] Merged {rel_path} into project root.")
                        except Exception as e:
                            print(f"[HARNESS] Warning: Failed to merge {rel_path}: {e}")
                    else:
                        # Move to real root
                        real_root_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(staged_pointer), str(real_root_file))
                        print(f"[HARNESS] Moved {rel_path} to project root.")
            
            shutil.rmtree(root_staging_dir)

        # --- Atomic Swap Execution ---
        if target_harness_dir.exists():
            from harness.init.minting_engine import perform_smart_merge
            print(f"\n[HARNESS] Existing harness found at {harness_folder}. Performing smart merge...")
            perform_smart_merge(target_harness_dir, temp_harness_dir)
            
            backup_dir = Path(args.project_path) / f"{harness_folder}.backup.{int(time.time())}"
            shutil.move(str(target_harness_dir), str(backup_dir))
            print(f"[HARNESS] Existing harness backed up to {backup_dir.name}")
            
            # Keep only the latest 3 backups
            backups = sorted(Path(args.project_path).glob(f"{harness_folder}.backup.*"))
            for old_backup in backups[:-3]:
                shutil.rmtree(old_backup)

        shutil.move(str(temp_harness_dir), str(target_harness_dir))
        
        # Format hooks dynamically now that they are in their final location
        adapter.install_hooks(Path(args.project_path))

        final_plugin_dir = target_harness_dir / "plugin-generated" if plugin_dir else None
        if final_plugin_dir:
            plugin_dir = str(final_plugin_dir)

        try:
            run_embedded_setup(
                Path(args.project_path),
                target_harness_dir,
                platform_choice,
                final_plugin_dir,
            )
        except HarnessSetupError as e:
            print(f"\n[HARNESS] ❌ ERROR: Embedded setup failed: {e}")
            langfuse_context.flush()
            sys.exit(1)

    finally:
        if temp_harness_dir.exists():
            shutil.rmtree(temp_harness_dir)


    print(f"\n\n{'='*60}")
    print("🚀 ONBOARDING COMPLETE")
    print(f"\n{'='*60}")
    
    counter = 1
    print(f"\n\n{counter}. Workspace Minted: {target_harness_dir}")
    counter += 1
    
    if plugin_dir:
        print(f"\n{counter}. Orchestrator Plugin Generated: {plugin_dir}")
        counter += 1
    
    print(f"\n\n{counter}. [ACTION REQUIRED] Context Automation:")
    print("   - The CodeGraph CI GitHub Action (.github/workflows/codegraph-ci.yml) has been generated.")
    counter += 1
        
    print(f"\n{'='*60}\n")
    langfuse_context.flush()

if __name__ == "__main__":
    main()
