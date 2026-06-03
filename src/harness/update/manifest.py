"""Ownership manifest — the bill-of-materials for `harness-wf update`.

Writes/reads `.harness-meta.json` inside the deployed plugin dir.  Extends the
PR #26 seed (harness_version + built_at) with:
  - render_context: the minimal inputs needed to reproduce templated files
  - owned: per-file {class, producer, source_path, source_hash, rendered_hash}

Hashing is normalized (LF line endings, trailing whitespace + trailing blank
lines stripped) so cross-platform/IDE noise does not produce false diffs.

Inputs:  plugin_dir (deployed), package_root (= src/harness/ of the installed
         tool, where upstream sources live), render_context (dict).
Outputs: the manifest dict (also written to disk).
Failure modes: an owned file whose source cannot be resolved gets
         source_hash=None (detection treats it as "unknown", never guesses).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from harness.update.classification import classify

META_FILENAME = ".harness-meta.json"


# --- normalization + hashing -------------------------------------------------

def _normalize(data: Union[bytes, str]) -> str:
    text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def normalize_and_hash(data: Union[bytes, str]) -> str:
    return hashlib.sha256(_normalize(data).encode("utf-8")).hexdigest()


def hash_file(path: Union[str, Path]) -> str:
    return normalize_and_hash(Path(path).read_bytes())


# --- version --------------------------------------------------------------

def _read_harness_version(package_root: Path) -> str:
    """Read version from the installed tool's pyproject.toml (single source).

    package_root is src/harness/; pyproject is two levels up (repo root) in the
    editable layout.  Falls back to walking parents for an installed package.
    """
    for candidate in (package_root.parent.parent / "pyproject.toml",
                       package_root.parent / "pyproject.toml"):
        if candidate.exists():
            try:
                with open(candidate, "rb") as f:
                    return tomllib.load(f)["project"]["version"]
            except Exception:
                pass
    return "0.0.0"


# --- writer / reader ---------------------------------------------------------

def _meta_path(plugin_dir_or_meta: Union[str, Path]) -> Path:
    p = Path(plugin_dir_or_meta)
    return p if p.name == META_FILENAME else p / META_FILENAME


def write_manifest(
    plugin_dir: Union[str, Path],
    package_root: Union[str, Path],
    render_context: dict,
    *,
    harness_version: Optional[str] = None,
) -> dict:
    """Walk plugin_dir, classify + hash every owned file, write the manifest."""
    plugin_dir = Path(plugin_dir)
    package_root = Path(package_root)

    existing = read_manifest(plugin_dir) if _meta_path(plugin_dir).exists() else {}
    version = harness_version or existing.get("harness_version") or _read_harness_version(package_root)

    owned: dict[str, dict] = {}
    for path in sorted(plugin_dir.rglob("*")):
        if not path.is_file():
            continue
        relpath = path.relative_to(plugin_dir).as_posix()
        ownership = classify(relpath)
        if ownership is None:
            continue

        source_hash = None
        if ownership.source_rel:
            src = package_root / ownership.source_rel
            if src.exists():
                source_hash = hash_file(src)

        owned[relpath] = {
            "class": ownership.cls,
            "producer": ownership.producer,
            "source_path": ownership.source_rel,
            "source_hash": source_hash,
            "rendered_hash": hash_file(path),
        }

    meta = {
        "harness_version": version,
        "built_at": existing.get("built_at") or datetime.now(timezone.utc).isoformat(),
        "render_context": render_context,
        "owned": owned,
    }

    _meta_path(plugin_dir).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def read_manifest(plugin_dir_or_meta: Union[str, Path]) -> dict:
    return json.loads(_meta_path(plugin_dir_or_meta).read_text(encoding="utf-8"))


# --- base sidecar (the 3-way merge base, customizable files only) -----------

BASE_DIR = ".harness-meta/base"


def write_base_sidecar(plugin_dir: Union[str, Path], manifest: dict) -> None:
    """Gzip the current on-disk bytes of every `customizable` owned file into
    `.harness-meta/base/<relpath>.gz`.  Only customizable files can conflict,
    so only they need a stored base — generated files overwrite, derived files
    regenerate.  Keeps the footprint to the markdown set."""
    plugin_dir = Path(plugin_dir)
    for relpath, entry in manifest.get("owned", {}).items():
        if entry.get("class") != "customizable":
            continue
        src = plugin_dir / relpath
        if not src.exists():
            continue
        dest = plugin_dir / BASE_DIR / (relpath + ".gz")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(gzip.compress(src.read_bytes()))


def read_base(plugin_dir: Union[str, Path], relpath: str) -> Optional[str]:
    """Return the stored base text for a customizable file, or None if absent."""
    p = Path(plugin_dir) / BASE_DIR / (relpath + ".gz")
    if not p.exists():
        return None
    return gzip.decompress(p.read_bytes()).decode("utf-8")
