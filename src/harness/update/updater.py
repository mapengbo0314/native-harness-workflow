"""Verdict engine for `harness-wf update` (R1 two-hash split).

Detection is read-only and needs NO rendering: it answers two independent
questions per file and looks the answer up in a truth table.

  we_changed  = upstream source hash now != source hash recorded at ship
  user_edited = on-disk rendered hash now != rendered hash recorded at ship

| we_changed | user_edited | verdict     |
|------------|-------------|-------------|
| no         | no          | current     |
| yes        | no          | apply       |
| no         | yes         | keep-yours  |
| yes        | yes         | conflict    |

Extra verdicts for cases the table doesn't cover:
  derived  — class==derived (regenerated from .md in apply; never compared)
  unknown  — owned but source unresolved (cannot decide; never guess)
  new-file — current upstream producer path absent from the old manifest
  requires-human — human decision required (customizable local-missing, or a
                   new upstream producer collides with an unmanifested local file)
  restore-missing — generated file absent on disk; restore from upstream
  regenerate-missing — derived file absent on disk; regenerate from sources
  removed-upstream — source recorded but gone from the installed package
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Union

from harness.update.classification import enumerate_source_producers
from harness.update.conflict import ConflictResolutionNeedsHuman, resolve
from harness.update.manifest import (
    META_FILENAME,
    read_base,
    read_manifest,
    hash_file,
    write_base_sidecar,
    write_manifest,
    _read_harness_version,
)

JOURNAL_FILENAME = ".harness-update-journal.json"
STAGING_DIRNAME = ".harness_update_tmp"


def verdict(we_changed: bool, user_edited: bool) -> str:
    if we_changed and user_edited:
        return "conflict"
    if we_changed:
        return "apply"
    if user_edited:
        return "keep-yours"
    return "current"


@dataclass(frozen=True)
class FileVerdict:
    relpath: str
    verdict: str
    cls: str


class UpdateRequiresHuman(RuntimeError):
    """Raised when update cannot proceed without a human decision."""


def plan_update(
    plugin_dir: Union[str, Path],
    package_root: Union[str, Path],
    manifest: Optional[dict] = None,
) -> list[FileVerdict]:
    """Compute a per-file verdict for every owned entry in the manifest.

    Read-only: hashes on-disk and upstream files, writes nothing.
    """
    plugin_dir = Path(plugin_dir)
    package_root = Path(package_root)
    if manifest is None:
        manifest = read_manifest(plugin_dir)

    manifest_owned = manifest.get("owned", {})
    current_producers = enumerate_source_producers(package_root)
    planned_relpaths = set(manifest_owned) | set(current_producers)

    results: list[FileVerdict] = []
    for relpath in sorted(planned_relpaths):
        entry = manifest_owned.get(relpath)
        current = current_producers.get(relpath)

        if entry is None:
            assert current is not None
            if (plugin_dir / relpath).exists():
                results.append(FileVerdict(relpath, "requires-human", current.cls))
                continue
            results.append(FileVerdict(relpath, "new-file", current.cls))
            continue

        cls = entry.get("class", "generated")
        producer = entry.get("producer")
        disk = plugin_dir / relpath
        if disk.exists() and not disk.is_file():
            results.append(FileVerdict(relpath, "requires-human", cls))
            continue

        if cls == "derived":
            if not disk.exists():
                results.append(FileVerdict(relpath, "regenerate-missing", cls))
                continue
            results.append(FileVerdict(relpath, "derived", cls))
            continue

        if producer == "emitted":
            if not disk.exists():
                results.append(FileVerdict(relpath, "restore-missing", cls))
                continue
            results.append(FileVerdict(relpath, "emitted", cls))
            continue

        source_path = entry.get("source_path")
        if not source_path:
            results.append(FileVerdict(relpath, "unknown", cls))
            continue

        src = package_root / source_path
        if not src.exists():
            results.append(FileVerdict(relpath, "removed-upstream", cls))
            continue

        if not disk.exists():
            results.append(FileVerdict(relpath, _missing_verdict(cls), cls))
            continue

        we_changed = hash_file(src) != entry.get("source_hash")
        user_edited = hash_file(disk) != entry.get("rendered_hash")
        results.append(FileVerdict(relpath, verdict(we_changed, user_edited), cls))

    return results


def _missing_verdict(cls: str) -> str:
    if cls == "customizable":
        return "requires-human"
    return "restore-missing"


def apply_update(
    plugin_dir: Union[str, Path],
    package_root: Union[str, Path],
    *,
    harness_dir: Union[str, Path],
    headless: bool = False,
    input_fn: Callable[[str], str] = input,
    editor: str | Callable[[Path], int | None] | None = None,
) -> list[FileVerdict]:
    """Apply a planned update transactionally.

    All conflict decisions are collected before staging, and all live writes go
    through a journaled commit so startup recovery can restore the pre-update
    state after an interrupted commit.
    """
    plugin_dir = Path(plugin_dir)
    package_root = Path(package_root)
    harness_dir = Path(harness_dir)
    recover_journal(plugin_dir)

    manifest = read_manifest(plugin_dir)
    _ensure_same_major(manifest, package_root)
    verdicts = plan_update(plugin_dir, package_root, manifest)

    blocking = [v for v in verdicts if v.verdict in {"requires-human", "unknown", "removed-upstream"}]
    if blocking:
        raise UpdateRequiresHuman(_format_blocking(blocking))

    if headless and any(v.verdict == "conflict" for v in verdicts):
        raise ConflictResolutionNeedsHuman("conflicts require interactive resolution")

    staging_dir = plugin_dir / STAGING_DIRNAME
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staged_plugin = staging_dir / "plugin"
    shutil.copytree(plugin_dir, staged_plugin, ignore=shutil.ignore_patterns(STAGING_DIRNAME))

    try:
        changed_relpaths = _resolve_into_staging(
            plugin_dir,
            staged_plugin,
            package_root,
            harness_dir,
            manifest,
            verdicts,
            headless=headless,
            input_fn=input_fn,
            editor=editor,
        )
        if not changed_relpaths:
            return verdicts

        extra_files = _stage_marketplace_manifest(harness_dir, staging_dir, package_root)
        staged_manifest = write_manifest(
            staged_plugin,
            package_root,
            render_context=manifest.get("render_context", {}),
            harness_version=_read_harness_version(package_root),
        )
        write_base_sidecar(staged_plugin, staged_manifest)
        metadata_relpaths = [META_FILENAME]
        metadata_relpaths.extend(
            path.relative_to(staged_plugin).as_posix()
            for path in sorted((staged_plugin / ".harness-meta" / "base").rglob("*.gz"))
        )
        _commit_staged_files(
            plugin_dir,
            staged_plugin,
            sorted(set(changed_relpaths + metadata_relpaths)),
            extra_files=extra_files,
        )
        _cleanup_journal(plugin_dir)
        return verdicts
    except Exception:
        recover_journal(plugin_dir)
        raise
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)


def recover_journal(plugin_dir: Union[str, Path]) -> None:
    """Restore pre-update files if a previous journaled commit was interrupted."""
    plugin_dir = Path(plugin_dir)
    journal = plugin_dir / JOURNAL_FILENAME
    if not journal.exists():
        return

    data = json.loads(journal.read_text(encoding="utf-8"))
    for entry in reversed(data.get("entries", [])):
        target = Path(entry["target"])
        backup = Path(entry["backup"])
        target.parent.mkdir(parents=True, exist_ok=True)
        if entry.get("existed"):
            if backup.exists():
                os.replace(backup, target)
        elif target.exists():
            target.unlink()

    journal.unlink(missing_ok=True)
    backup_root = plugin_dir / ".harness-meta" / "update-backups" / data.get("id", "")
    if backup_root.exists():
        shutil.rmtree(backup_root, ignore_errors=True)
    staging_dir = plugin_dir / STAGING_DIRNAME
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)


def _resolve_into_staging(
    plugin_dir: Path,
    staged_plugin: Path,
    package_root: Path,
    harness_dir: Path,
    manifest: dict,
    verdicts: list[FileVerdict],
    *,
    headless: bool,
    input_fn: Callable[[str], str],
    editor: str | Callable[[Path], int | None] | None,
) -> list[str]:
    changed: set[str] = set()
    owned = manifest.get("owned", {})

    for v in verdicts:
        if v.verdict in {"current", "keep-yours"}:
            continue
        if v.verdict in {"derived", "regenerate-missing"}:
            continue

        entry = owned.get(v.relpath)
        content = _produce_theirs(v.relpath, entry, package_root, manifest, staged_plugin)

        if v.verdict == "conflict":
            base = read_base(plugin_dir, v.relpath)
            if base is None:
                raise UpdateRequiresHuman(f"missing merge base for {v.relpath}")
            ours = (plugin_dir / v.relpath).read_text(encoding="utf-8")
            content = resolve(
                v.relpath,
                base,
                ours,
                content,
                headless=headless,
                input_fn=input_fn,
                editor=editor,
            )

        target = staged_plugin / v.relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        changed.add(v.relpath)

    if any(v.cls == "derived" or v.verdict in {"conflict", "apply", "new-file", "restore-missing"} for v in verdicts):
        from harness.init.plugin_generator import regenerate_derived

        regenerated = regenerate_derived(staged_plugin, harness_dir=harness_dir)
        changed.update(regenerated)

    return sorted(changed)


def _produce_theirs(
    relpath: str,
    entry: Optional[dict],
    package_root: Path,
    manifest: dict,
    staged_plugin: Path,
) -> str:
    if entry is None:
        from harness.update.classification import classify

        ownership = classify(relpath)
        if ownership is None:
            raise UpdateRequiresHuman(f"cannot reproduce unowned path {relpath}")
        entry = {
            "producer": ownership.producer,
            "source_path": ownership.source_rel,
            "class": ownership.cls,
        }

    producer = entry.get("producer")
    source_path = entry.get("source_path")
    context = manifest.get("render_context", {})
    platform = context.get("platform", "claude")

    if producer in {"runtime_copy", "emitted"} and relpath.startswith("src/"):
        from harness.init.runtime_slice import reproduce_runtime_file

        return reproduce_runtime_file(relpath.split("/", 1)[1], platform=platform, package_root=package_root)
    if producer == "emitted" and relpath == ".claude-plugin/plugin.json":
        existing = staged_plugin / relpath
        data = json.loads(existing.read_text(encoding="utf-8")) if existing.exists() else {}
        return json.dumps({**data, **_plugin_manifest_fragment(package_root)}, indent=2) + "\n"
    if producer == "template":
        if not source_path:
            raise UpdateRequiresHuman(f"missing template source for {relpath}")
        from harness.adapters import get_adapter
        from harness.init.render import render_template

        adapter = get_adapter(platform)
        source = package_root / source_path
        if relpath == "README.md":
            return source.read_text(encoding="utf-8").format(
                project_name=context.get("project_name", ".")
            )
        return render_template(
            source.read_text(encoding="utf-8"),
            file_path=str(source),
            target_root=package_root / "templates" / "boilerplate",
            target_dir_name=context.get("harness_dir_name", ".claude"),
            tool_replacements=adapter.get_tool_mappings(),
            jinja_context={
                "HARNESS_DIR": context.get("harness_dir_name", ".claude"),
                "subagent": adapter.get_subagent_text_call,
                "INGESTION_KEY": "",
                "PROJECT_SLUG": "",
            },
        )
    if producer == "verbatim":
        if not source_path:
            raise UpdateRequiresHuman(f"missing source for {relpath}")
        return (package_root / source_path).read_text(encoding="utf-8")

    raise UpdateRequiresHuman(f"cannot reproduce {relpath} with producer {producer!r}")


def _commit_staged_files(
    plugin_dir: Path,
    staged_plugin: Path,
    relpaths: list[str],
    *,
    extra_files: list[tuple[Path, Path]] | None = None,
) -> None:
    txid = uuid.uuid4().hex
    backup_root = plugin_dir / ".harness-meta" / "update-backups" / txid
    entries = []
    for relpath in relpaths:
        target = plugin_dir / relpath
        staged = staged_plugin / relpath
        backup = backup_root / relpath
        entries.append({
            "target": str(target),
            "staged": str(staged),
            "backup": str(backup),
            "existed": target.exists(),
        })
    for target, staged in extra_files or []:
        backup = backup_root / "__external__" / target.name
        entries.append({
            "target": str(target),
            "staged": str(staged),
            "backup": str(backup),
            "existed": target.exists(),
        })

    journal = plugin_dir / JOURNAL_FILENAME
    journal.write_text(json.dumps({"id": txid, "entries": entries}, indent=2) + "\n", encoding="utf-8")

    for entry in entries:
        target = Path(entry["target"])
        staged = Path(entry["staged"])
        backup = Path(entry["backup"])
        target.parent.mkdir(parents=True, exist_ok=True)
        backup.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            os.replace(target, backup)
        staged.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged, target)


def _cleanup_journal(plugin_dir: Path) -> None:
    journal = plugin_dir / JOURNAL_FILENAME
    if journal.exists():
        data = json.loads(journal.read_text(encoding="utf-8"))
        journal.unlink()
        backup_root = plugin_dir / ".harness-meta" / "update-backups" / data.get("id", "")
        if backup_root.exists():
            shutil.rmtree(backup_root, ignore_errors=True)


def _ensure_same_major(manifest: dict, package_root: Path) -> None:
    old = _parse_semver_major(manifest.get("harness_version"))
    new = _parse_semver_major(_read_harness_version(package_root))
    if old is None or new is None:
        raise UpdateRequiresHuman("harness version is absent or unparseable")
    if old != new:
        raise UpdateRequiresHuman("cross-major update requires migration or re-mint")


def _parse_semver_major(version: object) -> Optional[int]:
    if not isinstance(version, str):
        return None
    head = version.split(".", 1)[0]
    return int(head) if head.isdigit() else None


def _format_blocking(verdicts: list[FileVerdict]) -> str:
    return "human decision required: " + ", ".join(f"{v.verdict}:{v.relpath}" for v in verdicts)


def _plugin_manifest_fragment(package_root: Path) -> dict:
    version = _read_harness_version(package_root)
    return {
        "name": "orchestrator-plugin",
        "version": version,
    }


def _stage_marketplace_manifest(
    harness_dir: Path,
    staging_dir: Path,
    package_root: Path,
) -> list[tuple[Path, Path]]:
    path = harness_dir / ".claude-plugin" / "marketplace.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    plugins = data.setdefault("plugins", [])
    version = _read_harness_version(package_root)
    entry = {
        "name": "orchestrator-plugin",
        "source": "./harness-wf-plugin",
        "description": "Project-local orchestrator plugin for the generated harness",
        "version": version,
        "author": {"name": "E2G Harness"},
    }
    for idx, plugin in enumerate(plugins):
        if plugin.get("name") == "orchestrator-plugin":
            plugins[idx] = {**plugin, **entry}
            break
    else:
        plugins.append(entry)
    staged = staging_dir / "marketplace.json"
    staged.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return [(path, staged)]
