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
  missing  — recorded in manifest but absent on disk (user deleted)
  removed-upstream — source recorded but gone from the installed package
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from harness.update.manifest import read_manifest, hash_file


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

    results: list[FileVerdict] = []
    for relpath, entry in sorted(manifest.get("owned", {}).items()):
        cls = entry.get("class", "generated")
        disk = plugin_dir / relpath

        if not disk.exists():
            results.append(FileVerdict(relpath, "missing", cls))
            continue

        if cls == "derived":
            results.append(FileVerdict(relpath, "derived", cls))
            continue

        source_path = entry.get("source_path")
        if not source_path:
            results.append(FileVerdict(relpath, "unknown", cls))
            continue

        src = package_root / source_path
        if not src.exists():
            results.append(FileVerdict(relpath, "removed-upstream", cls))
            continue

        we_changed = hash_file(src) != entry.get("source_hash")
        user_edited = hash_file(disk) != entry.get("rendered_hash")
        results.append(FileVerdict(relpath, verdict(we_changed, user_edited), cls))

    return results
