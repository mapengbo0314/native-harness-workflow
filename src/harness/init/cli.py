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

# load_dotenv MUST run before any langfuse import so that LANGFUSE_ENABLED can
# take effect before the SDK initialises its background flush thread.
load_dotenv()

# Disable the Langfuse SDK when no credentials are present so it never tries
# to export spans and produce 401 noise.  Credentials can be supplied as either:
#   - HARNESS_GLOBAL_INGESTION_BASE64 (OTEL Authorization header, base64 pk:sk)
#   - LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY  (Python SDK direct)
_has_langfuse_creds = (
    os.environ.get("HARNESS_GLOBAL_INGESTION_BASE64")
    or (os.environ.get("LANGFUSE_SECRET_KEY") and os.environ.get("LANGFUSE_PUBLIC_KEY"))
)
if not _has_langfuse_creds:
    os.environ.setdefault("LANGFUSE_ENABLED", "false")

from langfuse import observe
from harness.runtime.langfuse_compat import langfuse_context


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


from pathlib import Path
from harness.adapters import get_adapter
from harness.domain.seed import run_domain_init, run_domain_refresh, _DEFAULT_MANIFEST_REL, _DEFAULT_REFERENCE_REL
from harness.domain.compiler import run_domain_compile

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
            cmd = [claude, "plugin", "validate", str(target)]
            result = subprocess.run(
                [claude, "plugin", "validate", str(target)],
                capture_output=True, 
                text=True,
                env=os.environ.copy()
            )
            if result.returncode != 0 and any(
                phrase in (result.stderr.lower() + result.stdout.lower())
                for phrase in ["unknown option", "not a valid flag", "strict"]
            ):
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True,
                    env=os.environ.copy()
                )
            if result.returncode != 0:
                raise HarnessSetupError(result.stdout + result.stderr)

    # Remove any __pycache__ / *.pyc artifacts that were created during
    # validation (e.g. exec_module() compiles dispatcher.py; hook scripts are
    # imported transitively).  Shipped bytecode is stale the moment the Python
    # version changes, and it bloats the plugin directory unnecessarily.
    for pycache_dir in plugin_dir.rglob("__pycache__"):
        shutil.rmtree(pycache_dir, ignore_errors=True)

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


def _write_update_metadata(
    plugin_dir: Optional[Path],
    *,
    platform: str,
    harness_dir_name: str,
    selected_agents: list[dict],
) -> None:
    """Stamp update ownership metadata after the final plugin layout exists."""
    if not plugin_dir or not plugin_dir.exists():
        return

    import harness
    from harness.update.manifest import write_base_sidecar, write_manifest

    package_root = Path(harness.__file__).parent
    manifest = write_manifest(
        plugin_dir,
        package_root,
        render_context={
            "platform": platform,
            "harness_dir_name": harness_dir_name,
            "selected_agents": selected_agents,
            "project_name": plugin_dir.parent.parent.name,
        },
    )
    write_base_sidecar(plugin_dir, manifest)
    print("[HARNESS] Update ownership manifest stamped.")


def parse_args():
    parser = argparse.ArgumentParser(description="Initialize or update a Harness agent workspace.")
    parser.add_argument("command", choices=["init", "update", "domain-init", "domain-refresh", "domain-compile"], help="Command to run")
    parser.add_argument("--project-path", required=True, help="Path to the repository")
    parser.add_argument("--bundle", help="Path to an existing CodeGraph bundle (.codegraph directory)")
    parser.add_argument("--check", action="store_true", help="(update) Dry-run: report stale/edited/conflicting files, write nothing")
    parser.add_argument("--force", action="store_true", help="(update) Force overwrite files modified locally that otherwise have a keep-yours verdict, and resolve conflicts by taking the new template")
    parser.add_argument("--force-major", action="store_true", help="(update) Allow applying updates across a MAJOR version boundary")
    parser.add_argument("--adopt", action="store_true", help="(update) Adopt an existing un-manifested harness by generating a base manifest from the current state")
    parser.add_argument("--platform", help="(update) Explicitly specify the platform to update (e.g. claude, gemini). Overrides auto-detection.")
    parser.add_argument(
        "--codegraph-exclusion",
        help="(init) Path to a gitignore-style file whose glob patterns are merged "
             "into .codegraph/config.json exclude[] before the initial index, so "
             "excluded code is never indexed.",
    )
    return parser.parse_args()


def _resolve_exclusion_file(args) -> Optional[str]:
    """Resolve --codegraph-exclusion to an existing path, or None."""
    raw = getattr(args, "codegraph_exclusion", None)
    if not raw:
        return None
    path = raw if os.path.isabs(raw) else os.path.join(args.project_path, raw)
    if not os.path.exists(path):
        print(f"\nWarning: --codegraph-exclusion file not found at {path}; ignoring.")
        return None
    return path


def _apply_codegraph_exclusions(codegraph_dir: str, exclusion_file: str) -> None:
    """Merge gitignore-style globs from `exclusion_file` into the CodeGraph
    config's exclude[] array. CodeGraph reads .codegraph/config.json on index,
    so patterns added here keep the listed code out of the graph."""
    config_path = os.path.join(codegraph_dir, "config.json")
    if not os.path.exists(config_path):
        print(f"Warning: CodeGraph config not found at {config_path}; cannot apply exclusions.")
        return

    patterns = []
    with open(exclusion_file, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line)
    if not patterns:
        return

    with open(config_path, encoding="utf-8") as fh:
        config = json.load(fh)
    exclude = config.setdefault("exclude", [])
    added = 0
    for pat in patterns:
        if pat not in exclude:
            exclude.append(pat)
            added += 1
    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)
    print(f"Applied {added} CodeGraph exclusion pattern(s) from {os.path.basename(exclusion_file)} -> {config_path}")


def run_update(args) -> None:
    """`harness-wf update` — in-place refresh of harness-owned files.
    """
    import harness
    from harness.adapters.profile import load_profile
    from harness.update.manifest import META_FILENAME, write_manifest, write_base_sidecar, read_manifest
    from harness.update.conflict import ConflictResolutionAborted, ConflictResolutionNeedsHuman
    from harness.update.updater import UpdateRequiresHuman, apply_update, plan_update, recover_journal, _migrate_b0_paths

    project = Path(args.project_path)
    
    # Auto-detect active platform
    import json
    from harness.adapters.profile import load_profile, _DEFAULT_PROFILES_PATH
    
    detected_platform = getattr(args, "platform", None)
    
    with open(_DEFAULT_PROFILES_PATH, encoding="utf-8") as fh:
        profiles_data = json.load(fh)
        
    if not detected_platform:
        for plat, data in profiles_data.items():
            if (project / data["config_dir"]).exists():
                detected_platform = plat
                break
            
    if not detected_platform:
        print("[HARNESS] No harness configuration found. Please run `harness-wf init` first.")
        sys.exit(2)
        
    try:
        profile = load_profile(detected_platform)
    except Exception as e:
        print(f"[HARNESS] Error loading profile for platform '{detected_platform}': {e}")
        sys.exit(2)
    
    # Fast-fail if the detected platform does not support in-place plugin updates
    if not profile.supports_plugin:
        print(f"[HARNESS] Found {profile.config_dir} directory.")
        print("[HARNESS] In-place updates via `update` are currently only supported for platforms with a plugin structure (e.g. Claude).")
        print(f"[HARNESS] To update your {profile.config_dir} workspace, please run `harness-wf init --project-path .` to perform a smart merge.")
        sys.exit(2)
        
    harness_dir = project / profile.config_dir
    plugin_dir = project / profile.config_dir / str(profile.plugin_dir_name)

    if not plugin_dir.exists():
        if getattr(args, "adopt", False):
            print(f"[HARNESS] Cannot adopt: {plugin_dir} does not exist.")
            sys.exit(2)
        else:
            print(f"[HARNESS] {plugin_dir} is missing. Please run `harness-wf init` to re-mint the workspace.")
            sys.exit(2)

    package_root = Path(harness.__file__).parent
    recover_journal(plugin_dir)

    if not (plugin_dir / META_FILENAME).exists():
        if getattr(args, "adopt", False):
            print("[HARNESS] Adopting existing workspace by synthesizing manifest...")
            manifest = write_manifest(
                plugin_dir,
                package_root,
                render_context={"harness_dir_name": profile.config_dir, "platform": profile.platform_name, "selected_agents": []}
            )
            write_base_sidecar(plugin_dir, manifest)
            print("[HARNESS] Manifest synthesized. Proceeding with update...")
        else:
            print(f"[HARNESS] No ownership manifest at {plugin_dir / META_FILENAME}.")
            print("[HARNESS] This harness predates update support — run a full re-mint (`harness-wf init`).")
            sys.exit(2)

    if not args.check:
        try:
            verdicts = apply_update(
                plugin_dir,
                package_root,
                harness_dir=harness_dir,
                headless=os.environ.get("HARNESS_HEADLESS") == "1",
                force=args.force,
                force_major=args.force_major,
            )
        except (ConflictResolutionAborted, ConflictResolutionNeedsHuman, UpdateRequiresHuman) as exc:
            print(f"[HARNESS] update requires attention: {exc}")
            sys.exit(2)
        counts: dict[str, int] = {}
        for v in verdicts:
            counts[v.verdict] = counts.get(v.verdict, 0) + 1
        summary = ", ".join(f"{k}={n}" for k, n in sorted(counts.items()))
        print(f"[HARNESS] update applied — {summary or 'no changes'}")
        return

    from harness.update.manifest import read_manifest
    from harness.update.updater import _migrate_b0_paths
    manifest = read_manifest(plugin_dir)
    _migrate_b0_paths(manifest, harness_dir, plugin_dir, package_root, dry_run=True)
    verdicts = plan_update(plugin_dir, package_root, manifest, force=args.force)
    needs_attention = {"conflict", "requires-human", "unknown", "removed-upstream"}
    counts: dict[str, int] = {}
    print(f"[HARNESS] update --check  ({plugin_dir})\n")
    for v in verdicts:
        counts[v.verdict] = counts.get(v.verdict, 0) + 1
        print(f"  {v.verdict:<16} {v.relpath}")
    summary = ", ".join(f"{k}={n}" for k, n in sorted(counts.items()))
    print(f"\n[HARNESS] {len(verdicts)} owned files — {summary or 'none'}")
    if any(c in counts for c in needs_attention):
        print("[HARNESS] Some files need a human decision (conflict/requires-human/unknown/removed-upstream).")


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

    # `update` is a distinct lifecycle from `init`: it does not need npx,
    # CodeGraph, platform selection, or the atomic-swap machinery.
    if args.command == "update":
        run_update(args)
        langfuse_context.flush()
        return

    # `domain-init` / `domain-compile` are offline, plugin-scoped; no npx/CodeGraph.
    if args.command == "domain-init":
        run_domain_init(args.project_path)
        langfuse_context.flush()
        return

    if args.command == "domain-refresh":
        run_domain_refresh(args.project_path)
        langfuse_context.flush()
        return

    if args.command == "domain-compile":
        proj = Path(args.project_path)
        run_domain_compile(
            proj,
            manifest_path=proj / _DEFAULT_MANIFEST_REL,
            reference_dir=proj / _DEFAULT_REFERENCE_REL,
        )
        langfuse_context.flush()
        return

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

            exclusion_file = _resolve_exclusion_file(args)
            if exclusion_file:
                # Split init from index so the exclusion patterns land in
                # config.json BEFORE the first index runs — no force re-index.
                subprocess.run(
                    ["npx", "--yes", "@colbymchenry/codegraph", "init"],
                    cwd=args.project_path, env=env, check=True,
                )
                _apply_codegraph_exclusions(default_codegraph_dir, exclusion_file)
                subprocess.run(
                    ["npx", "--yes", "@colbymchenry/codegraph", "index"],
                    cwd=args.project_path, env=env, check=True,
                )
            else:
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
    else:
        # DB already present — still honor a newly supplied exclusion file by
        # merging it into config.json. No re-index here (per "no force"); the
        # running serve watcher / next natural sync applies the updated config.
        exclusion_file = _resolve_exclusion_file(args)
        if exclusion_file:
            _apply_codegraph_exclusions(codegraph_dir, exclusion_file)
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

    if harness_folder == ".claude":
        from harness.adapters.profile import load_profile as _load_profile
        from harness.update.updater import recover_journal

        recover_journal(target_harness_dir / _load_profile("claude").plugin_dir_name)
    
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

        from harness.adapters.profile import load_profile as _load_profile
        _claude_plugin_dir_name = _load_profile("claude").plugin_dir_name
        final_plugin_dir = target_harness_dir / _claude_plugin_dir_name if plugin_dir else None
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

        _write_update_metadata(
            final_plugin_dir,
            platform=adapter.get_platform_name(),
            harness_dir_name=harness_folder,
            selected_agents=selected_agents,
        )

    finally:
        if temp_harness_dir.exists():
            shutil.rmtree(temp_harness_dir)

    # Scaffold the project-ops manifest + reference docs dir (best-effort).
    try:
        run_domain_init(args.project_path)
    except Exception as e:
        print(f"[HARNESS] Warning: domain scaffold skipped: {e}")

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
    print("   - Run npx -y @colbymchenry/codegraph init --index in the root of your project.")
    counter += 1
        
    print(f"\n{'='*60}\n")
    langfuse_context.flush()

if __name__ == "__main__":
    main()
