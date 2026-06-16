import argparse
import importlib.util
import json
import shlex
import sys
import os
import subprocess
import shutil
import uuid
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# load_dotenv MUST run before any langfuse import so that LANGFUSE_ENABLED can
# take effect before the SDK initialises its background flush thread.
load_dotenv()

# Disable the Langfuse SDK when no credentials are present so it never tries
# to export spans and produce auth-warning noise.  Credentials can be supplied
# as either:
#   - HARNESS_GLOBAL_INGESTION_BASE64 (OTEL Authorization header, base64 pk:sk)
#   - LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY  (Python SDK direct)
def _disable_langfuse_unless_configured(environ=os.environ) -> None:
    has_creds = (
        environ.get("HARNESS_GLOBAL_INGESTION_BASE64")
        or (environ.get("LANGFUSE_SECRET_KEY") and environ.get("LANGFUSE_PUBLIC_KEY"))
    )
    if not has_creds:
        environ.setdefault("LANGFUSE_ENABLED", "false")          # harness compat gate (langfuse_compat.py)
        environ.setdefault("LANGFUSE_TRACING_ENABLED", "false")  # langfuse v3+/v4 SDK kill-switch

_disable_langfuse_unless_configured()

from langfuse import observe
from harness.runtime.langfuse_compat import langfuse_context


class HarnessSetupError(RuntimeError):
    """Raised when mandatory one-step harness setup cannot be completed."""


def _post_mint_domain_init(project_path, platform: str, *, run_init=None):
    """Scaffold the project-ops manifest under the active platform's deployed
    root (best-effort). Threads `platform` so seed.py resolves the correct
    config dir (e.g. .gemini/domain/domain.json for a gemini mint)."""
    if run_init is None:
        run_init = run_domain_init  # resolved lazily (imported below in this module)
    result = run_init(project_path, platform=platform)
    # The mint-time pack install ran with the stack unknown (fail-open: no
    # prune).  Now that the seed has written domain.json, re-run selection so
    # the deployed packs and mirror reflect the detected stack.  Claude only:
    # sync_rules_packs assumes the claude plugin layout; non-claude platforms
    # get pack content via persona inlining at mint time.
    if platform == "claude":
        try:
            sync_rules_packs(str(project_path))
        except Exception as exc:
            print(f"[HARNESS] Warning: post-seed pack sync failed: {exc}")
    return result


def _domain_next_steps(platform: str) -> str:
    """Post-init guidance for the project-ops manifest: where to drop product
    docs and how to compile them into domain.json. Paths come from the same
    rule the scaffold used (seed._platform_paths)."""
    _, reference_rel = _platform_paths(platform)
    return (
        "   The project-ops manifest (domain.json) was scaffolded with your detected stack.\n"
        "   Two steps to finish it:\n"
        f"   a) Drop your product docs (PRD, direction, business goals) into {reference_rel}/\n"
        f"   b) Run: harness-wf domain-compile --project-path . --platform {platform}\n"
        "      This distills them into domain.json's `business` section, which agents\n"
        "      pull via the `domain` MCP tool (domain_ops). Re-run it whenever the docs change."
    )


from harness.adapters import get_adapter
from harness.init.platforms import platform_name_from_choice, harness_folder_from_choice
from harness.domain.seed import run_domain_init, run_domain_refresh, _platform_paths
from harness.domain.compiler import run_domain_compile
from harness.init.features import compile_features, FeaturesValidationError

def _run_plugin_validate(claude: str, target: Path) -> None:
    """Run `claude plugin validate <target>` once, failing loudly on error.

    review 2026-06-12 (C3): the previous version retried by re-running an
    identical command — no flag was ever degraded, so the retry could never
    behave differently. Single run, no retry.
    """
    result = subprocess.run(
        [claude, "plugin", "validate", str(target)],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        raise HarnessSetupError(result.stdout + result.stderr)


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
            _run_plugin_validate(claude, Path(target))

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
    enable_rtk: bool = False,
    install_rtk: bool = False,
) -> None:
    print("\n[HARNESS] Running embedded setup...")
    if sys.version_info < (3, 8):
        raise HarnessSetupError("Python 3.8+ is required.")

    adapter = get_adapter(platform_name_from_choice(platform_choice))
    adapter.configure_cli(project_path)

    if enable_rtk:
        from harness.init.rtk import setup_rtk

        try:
            setup_rtk(
                project_path,
                adapter.get_platform_name(),
                install_if_missing=install_rtk,
                interactive=os.environ.get("HARNESS_HEADLESS") != "1",
            )
        except ValueError as exc:
            print(f"[HARNESS] Warning: {exc} Continuing without RTK.")
    
    if plugin_dir and plugin_dir.exists():
        _validate_claude_plugin(project_path, plugin_dir)

    print("[HARNESS] Embedded setup complete.")


def _write_update_metadata(
    plugin_dir: Optional[Path],
    *,
    platform: str,
    harness_dir_name: str,
    selected_agents: list[dict],
    rules_packs: Optional[dict] = None,
) -> None:
    """Stamp update ownership metadata after the final plugin layout exists.

    Parameters
    ----------
    rules_packs:
        Optional ``{"selected": [...], "enabled": bool}`` dict describing which
        language packs were selected at mint time.  Persisted into
        ``render_context`` so ``plan_update`` can filter pack producers on
        subsequent updates (Phase 1b).
    """
    if not plugin_dir or not plugin_dir.exists():
        return

    import harness
    from harness.update.manifest import write_base_sidecar, write_manifest

    package_root = Path(harness.__file__).parent
    rc: dict = {
        "platform": platform,
        "harness_dir_name": harness_dir_name,
        "selected_agents": selected_agents,
        "project_name": plugin_dir.parent.parent.name,
    }
    if rules_packs is not None:
        rc["rules_packs"] = rules_packs
    manifest = write_manifest(
        plugin_dir,
        package_root,
        render_context=rc,
    )
    write_base_sidecar(plugin_dir, manifest)
    print("[HARNESS] Update ownership manifest stamped.")


def _print_features_result(result, plugin_root: Path) -> None:
    """Print the standard features-sync outcome line."""
    if result is not None:
        print(f"[HARNESS] features.json compiled -> {result}")
    else:
        print(f"[HARNESS] No features.yaml found at {plugin_root}; nothing to compile.")


def run_features_sync(project_path: str) -> None:
    """Compile ``features.yaml`` -> ``features.json`` for the given plugin root.

    Exposed as ``harness-wf features sync --project-path <path>``.
    """
    plugin_root = Path(project_path)
    try:
        result = compile_features(plugin_root)
    except FeaturesValidationError as exc:
        print(f"[HARNESS] ERROR: {exc}")
        sys.exit(1)
    _print_features_result(result, plugin_root)


def sync_rules_packs(project_path: str, *, plugin_root: Optional[Path] = None) -> None:
    """Re-run pack selection and install for the project.

    Called by ``run_domain_refresh_with_sync`` so that a stack change (detected
    during domain-refresh) is reflected in the deployed packs.

    Parameters
    ----------
    project_path:
        The user's project root (where ``.claude/`` lives).
    plugin_root:
        Optional explicit plugin root; defaults to
        ``<project>/.claude/harness-wf-plugin``.
    """
    from harness.init.minting_engine import install_rules_packs

    project = Path(project_path)
    resolved_plugin_root = plugin_root or (project / ".claude" / "harness-wf-plugin")

    # Read compiled features (best-effort; default-enabled when absent)
    features: dict = {}
    features_json = resolved_plugin_root / "features.json"
    if features_json.exists():
        try:
            features = json.loads(features_json.read_text(encoding="utf-8"))
        except Exception:
            features = {}

    packs_root = resolved_plugin_root / "rules" / "packs"
    if not packs_root.exists():
        return  # nothing to sync; packs not shipped in this deploy

    install_rules_packs(
        project_path=project,
        deployed_plugin_path=resolved_plugin_root,
        packs_root=packs_root,
        features=features,
    )


def _compute_rules_packs_rc(project_path: Path, plugin_root: Path, features: dict) -> dict:
    """Compute the ``{"selected": [...], "enabled": bool}`` dict for the manifest.

    Reuses the same computation as the mint call site so the two are kept in
    sync.  Fail-open: if anything goes wrong, returns the features-enabled flag
    with an empty selection.

    Parameters
    ----------
    project_path:
        The user's project root (used to read domain.json for stack detection).
    plugin_root:
        Root of the deployed plugin (passed to minting_engine helpers).
    features:
        Parsed features dict (may be empty).
    """
    try:
        from harness.init.minting_engine import (
            _read_domain_stack,
            _features_rules_packs_enabled,
            _features_language_enabled,
        )
        from harness.init.lang_aliases import stack_to_packs

        rp_on = _features_rules_packs_enabled(features)
        if rp_on:
            stack = _read_domain_stack(project_path)
            if stack:
                matched = sorted(
                    p for p in stack_to_packs(stack)
                    if _features_language_enabled(features, p)
                )
            else:
                # Stack unknown (domain.json missing or has no stack key).
                # Emit None so the update filter treats this as fail-open rather
                # than "no languages wanted".  If the stack is known but matches
                # nothing, [] is correct (explicit empty selection).
                matched = None
        else:
            matched = []
        return {"selected": matched, "enabled": rp_on}
    except Exception as exc:
        print(f"[HARNESS] Warning: could not compute rules_packs for manifest: {exc}")
        return {"selected": None, "enabled": True}


def run_domain_refresh_with_sync(
    project_path: str,
    *,
    platform: Optional[str] = None,
) -> None:
    """Run domain-refresh then sync features.yaml -> features.json and
    rewrite the manifest's render_context.rules_packs so the stack filter
    stays current after a domain-refresh."""
    run_domain_refresh(project_path, platform=platform)
    # Deployed plugin dir is always <project>/.claude/harness-wf-plugin — the
    # features.yaml and rules/packs live there, not at the project root.
    plugin_root = Path(project_path) / ".claude" / "harness-wf-plugin"
    try:
        result = compile_features(plugin_root)
    except FeaturesValidationError as exc:
        print(f"[HARNESS] ERROR: {exc}")
        sys.exit(1)
    _print_features_result(result, plugin_root)
    # Pass the same plugin_root that compile_features used so pack selection
    # reads the features.json it just wrote, not a different deployed dir.
    sync_rules_packs(project_path, plugin_root=plugin_root)

    # Recompute and persist rules_packs selection into the manifest so
    # plan_update's pack filter reflects the refreshed stack.  Fail-open.
    try:
        from harness.update.manifest import read_manifest, META_FILENAME, write_manifest as _wm
        import harness as _harness

        # Deployed plugin dir is always <project>/.claude/harness-wf-plugin
        project = Path(project_path)
        deployed_plugin = project / ".claude" / "harness-wf-plugin"
        meta = deployed_plugin / META_FILENAME
        if not meta.exists():
            return  # no manifest to update

        # Read features that sync_rules_packs just worked with
        features: dict = {}
        features_json = deployed_plugin / "features.json"
        if features_json.exists():
            try:
                features = json.loads(features_json.read_text(encoding="utf-8"))
            except Exception:
                features = {}

        # Compute new selection from the refreshed stack
        new_rp = _compute_rules_packs_rc(project, deployed_plugin, features)

        # Read manifest, update only render_context.rules_packs, write back
        existing = read_manifest(deployed_plugin)
        rc = dict(existing.get("render_context", {}))
        rc["rules_packs"] = new_rp

        package_root = Path(_harness.__file__).parent
        _wm(
            deployed_plugin,
            package_root,
            render_context=rc,
            harness_version=existing.get("harness_version"),
        )
        print(f"[HARNESS] Manifest rules_packs filter updated: selected={new_rp['selected']}")
    except Exception as exc:
        print(f"[HARNESS] Warning: manifest rules_packs refresh failed: {exc}")


def parse_args():
    parser = argparse.ArgumentParser(description="Initialize or update a Harness agent workspace.")
    parser.add_argument("command", choices=["init", "update", "domain-init", "domain-refresh", "domain-compile", "features"], help="Command to run")
    parser.add_argument("subcommand", nargs="?", help="Subcommand (e.g. 'sync' for features)")
    parser.add_argument("--project-path", required=True, help="Path to the repository")
    parser.add_argument("--bundle", help="Path to an existing CodeGraph bundle (.codegraph directory)")
    parser.add_argument("--check", action="store_true", help="(update) Dry-run: report stale/edited/conflicting files, write nothing")
    parser.add_argument("--force", action="store_true", help="(update) Force overwrite files modified locally that otherwise have a keep-yours verdict, and resolve conflicts by taking the new template")
    parser.add_argument("--force-major", action="store_true", help="(update) Allow applying updates across a MAJOR version boundary")
    parser.add_argument("--adopt", action="store_true", help="(update) Adopt an existing un-manifested harness by generating a base manifest from the current state")
    parser.add_argument(
        "--platform",
        choices=["claude", "gemini", "codex", "cursor", "generic"],
        help="(update) Explicitly specify the platform to update (claude, gemini, codex, cursor, generic). Overrides auto-detection.",
    )
    parser.add_argument(
        "--codegraph-exclusion",
        help="(init) Path to a gitignore-style file whose glob patterns are merged "
             "into .codegraph/config.json exclude[] before the initial index, so "
             "excluded code is never indexed.",
    )
    parser.add_argument(
        "--rtk",
        action="store_true",
        help="Enable optional RTK shell-output compression in the minted harness.",
    )
    parser.add_argument(
        "--install-rtk",
        action="store_true",
        help="Install RTK automatically if missing; implies --rtk.",
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
    from harness.update.manifest import META_FILENAME, write_manifest, write_base_sidecar, read_manifest
    from harness.update.conflict import ConflictResolutionAborted, ConflictResolutionNeedsHuman
    from harness.update.updater import UpdateRequiresHuman, apply_update, plan_update, recover_journal, _migrate_b0_paths

    project = Path(args.project_path)
    
    # Auto-detect active platform
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
                project_root=project,
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
    # An explicit --platform threads the per-platform deployed root through so a
    # non-claude workspace reads/writes domain.json under its own config dir;
    # absent the flag, behaviour is the legacy claude default (unchanged).
    _domain_platform = getattr(args, "platform", None)

    if args.command == "domain-init":
        run_domain_init(args.project_path, platform=_domain_platform)
        langfuse_context.flush()
        return

    if args.command == "domain-refresh":
        run_domain_refresh_with_sync(args.project_path, platform=_domain_platform)
        langfuse_context.flush()
        return

    if args.command == "features":
        sub = getattr(args, "subcommand", None)
        if sub == "sync":
            run_features_sync(args.project_path)
        else:
            print(f"[HARNESS] Unknown features subcommand: {sub!r}. Use 'sync'.")
            sys.exit(1)
        langfuse_context.flush()
        return

    if args.command == "domain-compile":
        proj = Path(args.project_path)
        # Same path-resolution rule as domain-init/refresh (seed._platform_paths).
        manifest_rel, reference_rel = _platform_paths(_domain_platform)
        manifest_path = proj / manifest_rel
        reference_dir = proj / reference_rel
        run_domain_compile(
            proj,
            manifest_path=manifest_path,
            reference_dir=reference_dir,
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
    install_rtk = (
        getattr(args, "install_rtk", False) is True
        or os.environ.get("HARNESS_INSTALL_RTK") == "1"
    )
    enable_rtk = (
        getattr(args, "rtk", False) is True
        or os.environ.get("HARNESS_RTK") == "1"
        or install_rtk
    )

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
    
    harness_folder = harness_folder_from_choice(platform_choice)

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
            logical_harness_name=harness_folder,
            enable_rtk=enable_rtk,
        )

        adapter = get_adapter(platform_name_from_choice(platform_choice))

        # Copy runtime modules baked for the selected platform only
        from harness.init.minting_engine import copy_runtime_modules
        copy_runtime_modules(temp_harness_dir, platform_id=platform_name_from_choice(platform_choice))

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

        # Re-compile features.yaml -> features.json after the smart merge so the
        # JSON always reflects the merged YAML (never a stale pre-merge artifact).
        _compile_root = final_plugin_dir if final_plugin_dir else target_harness_dir
        _recompiled_features: dict = {}
        try:
            from harness.init.features import compile_features as _compile_features
            _json_path = _compile_features(_compile_root)
            if _json_path:
                print(f"[HARNESS] features.json recompiled at {_json_path}")
                try:
                    import json as _json_mod
                    _recompiled_features = _json_mod.loads(Path(_json_path).read_text(encoding="utf-8"))
                except Exception:
                    _recompiled_features = {}
        except Exception as _e:
            print(f"[HARNESS] Warning: features recompile failed: {_e}")

        # Re-sync rules packs after the re-mint so the deployed packs match the
        # (possibly updated) features.yaml toggle state (Phase 1a ECC port).
        try:
            from harness.init.minting_engine import install_rules_packs as _install_rp
            _packs_root = _compile_root / "rules" / "packs"
            if _packs_root.exists():
                _install_rp(
                    project_path=Path(args.project_path),
                    deployed_plugin_path=_compile_root,
                    packs_root=_packs_root,
                    features=_recompiled_features,
                )
                print(f"[HARNESS] Rules packs re-synced.")
        except Exception as _e:
            print(f"[HARNESS] Warning: rules packs re-sync failed: {_e}")

        try:
            run_embedded_setup(
                Path(args.project_path),
                target_harness_dir,
                platform_choice,
                final_plugin_dir,
                enable_rtk=enable_rtk,
                install_rtk=install_rtk,
            )
        except HarnessSetupError as e:
            print(f"\n[HARNESS] ❌ ERROR: Embedded setup failed: {e}")
            langfuse_context.flush()
            sys.exit(1)

        # Compute rules_packs selection for manifest (Phase 1b: persist stack filter).
        _rules_packs_rc: Optional[dict] = _compute_rules_packs_rc(
            Path(args.project_path),
            final_plugin_dir if final_plugin_dir else target_harness_dir,
            _recompiled_features,
        )

        _write_update_metadata(
            final_plugin_dir,
            platform=adapter.get_platform_name(),
            harness_dir_name=harness_folder,
            selected_agents=selected_agents,
            rules_packs=_rules_packs_rc,
        )

    finally:
        if temp_harness_dir.exists():
            shutil.rmtree(temp_harness_dir)

    # Scaffold the project-ops manifest + reference docs dir (best-effort).
    # Thread the active platform so the manifest lands under the right config
    # dir (.claude/harness-wf-plugin for claude, .gemini/.cursor/.codex else).
    domain_scaffolded = False
    try:
        _post_mint_domain_init(args.project_path, adapter.get_platform_name())
        domain_scaffolded = True
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

    if domain_scaffolded:
        print(f"\n{counter}. [ACTION REQUIRED] Project-Ops Manifest:")
        try:
            print(_domain_next_steps(adapter.get_platform_name()))
        except Exception:
            print("   Drop product docs into your platform's docs/reference dir, then run harness-wf domain-compile.")
        counter += 1

    print(f"\n{'='*60}\n")
    langfuse_context.flush()

if __name__ == "__main__":
    main()
