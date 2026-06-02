"""Ownership classification — the leash for `harness-wf update`.

Pure, no I/O.  Maps a deployed path (relative to the plugin dir,
e.g. ``.claude/harness-wf-plugin/``) to how the harness owns it:

    class     : generated | customizable | derived
    producer  : template | runtime_copy | export | emitted | verbatim
    source_rel: package-relative upstream path (under ``src/harness/``),
                or None for emitted/derived files that have no single source.

`classify()` returns None when a path is excluded (pollution/secret/self) OR
is not a harness producer-path at all (user files stay invisible to update).

Failure modes: a brand-new harness file with no rule falls through to None
(invisible) — conservative; it simply won't be delivered by detection until a
rule is added.  This is intentional: update never touches a path it cannot
positively identify as harness-owned.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Optional

from harness.init.runtime_slice import RUNTIME_FILE_MAP


@dataclass(frozen=True)
class Ownership:
    cls: str               # generated | customizable | derived
    producer: str          # template | runtime_copy | export | emitted | verbatim
    source_rel: Optional[str]


# --- exclusions: pollution, secrets, and update's own bookkeeping -----------

EXCLUDE_GLOBS: tuple[str, ...] = (
    "state", "state/*",
    "logs", "logs/*",
    ".venv", ".venv/*",
    ".deepeval", ".deepeval/*",
    "*__pycache__*",
    "*.pyc",
    "harness.db",
    "uv.lock",
    ".env.telemetry-harness",
    ".harness-meta.json",
    ".harness-update-journal.json",
    ".harness-meta/*",
)


def _strip_prefix(relpath: str) -> str:
    """Strip a leading ``./`` only — never leading dots (``.deepeval`` must stay)."""
    while relpath.startswith("./"):
        relpath = relpath[2:]
    return relpath


def is_excluded(relpath: str) -> bool:
    relpath = _strip_prefix(relpath)
    return any(fnmatch.fnmatch(relpath, pat) for pat in EXCLUDE_GLOBS)


# --- runtime slice (copied/emitted by copy_runtime_modules) -----------------
# deployed ``src/<name>`` -> package-relative source under src/harness/.
# None == emitted at mint time (no single upstream file).
#
# D5: This map is derived from RUNTIME_FILE_MAP (single source of truth in
# harness.init.runtime_slice).  The shape is preserved identically so that all
# callers of RUNTIME_SOURCE_MAP continue to work unchanged.

RUNTIME_SOURCE_MAP: dict[str, Optional[str]] = {
    f"src/{name}": source_rel
    for name, source_rel in RUNTIME_FILE_MAP.items()
}

# Derived JSON projections regenerated from .md via export_*_config.
DERIVED_FILES: frozenset[str] = frozenset({"agents.json", "rules.json", "orchestrator.json"})

# D8 — declarative mapping: derived JSON filename -> source dir/file (plugin-relative).
# Each value is the relpath of the .md source that produces the corresponding JSON.
# agents/ and rules/ are directories; orchestrator.md is a single file in harness_dir.
DERIVED_FROM: dict[str, str] = {
    "agents.json": "agents",
    "rules.json": "rules",
    "orchestrator.json": "orchestrator.md",
}

# Emitted plugin manifests with no single template source.
EMITTED_GENERATED: frozenset[str] = frozenset({
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
})

# Boilerplate-derived directories whose subpath is identity under the package
# templates/boilerplate/ tree.  (cls, producer) per dir.
_BOILERPLATE_DIRS: dict[str, tuple[str, str]] = {
    "skills": ("customizable", "template"),
    "agents": ("customizable", "template"),
    "hooks": ("generated", "template"),
    "scripts": ("generated", "template"),
    "rules": ("customizable", "template"),
}

# Single boilerplate-derived files at the plugin root.
_BOILERPLATE_FILES: dict[str, tuple[str, str, str]] = {
    # deployed relpath -> (cls, producer, source_rel)
    "pyproject.toml": ("generated", "verbatim", "templates/boilerplate/pyproject.toml"),
    "README.md": ("generated", "template", "templates/boilerplate/README.md.template"),
    # Static harness config files relocated into the plugin (not to be confused with
    # agents.json which is plural and derived).
    "agent.json": ("generated", "template", "templates/boilerplate/agent.json"),
    "skills.json": ("generated", "template", "templates/boilerplate/skills.json"),
}


def _first_segment(relpath: str) -> str:
    return relpath.split("/", 1)[0]


def classify(relpath: str) -> Optional[Ownership]:
    """Return Ownership for a deployed plugin-relative path, or None if the
    path is excluded or not a recognised harness producer-path."""
    relpath = _strip_prefix(relpath)
    if not relpath or is_excluded(relpath):
        return None

    # Runtime slice.
    if relpath in RUNTIME_SOURCE_MAP:
        src = RUNTIME_SOURCE_MAP[relpath]
        return Ownership("generated", "emitted" if src is None else "runtime_copy", src)
    if _first_segment(relpath) == "src":
        # Unknown future runtime file: owned + generated, but source unknown.
        return Ownership("generated", "runtime_copy", None)

    # Derived JSON projections.
    if relpath in DERIVED_FILES:
        return Ownership("derived", "export", None)

    # Emitted plugin manifests.
    if relpath in EMITTED_GENERATED:
        return Ownership("generated", "emitted", None)

    # Single boilerplate files at the plugin root.
    if relpath in _BOILERPLATE_FILES:
        cls, producer, source_rel = _BOILERPLATE_FILES[relpath]
        return Ownership(cls, producer, source_rel)

    # Boilerplate-derived directories (identity subpath under templates/boilerplate/).
    seg = _first_segment(relpath)
    if seg in _BOILERPLATE_DIRS and "/" in relpath:
        cls, producer = _BOILERPLATE_DIRS[seg]
        return Ownership(cls, producer, f"templates/boilerplate/{relpath}")

    # Not a recognised harness path -> invisible to update.
    return None
