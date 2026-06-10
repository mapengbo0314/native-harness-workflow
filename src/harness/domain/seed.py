"""harness.domain.seed — `harness-wf domain-init`.

Detect the stack (via `detect`) and scaffold `domain.json` inside the plugin:
`stack` filled, the manual sections (`environments`/`test`/`deploy`/`infra`) left
as empty slots for engineers to fill, and `references` pre-suggested from the
repo's conventional docs (first H1 as the label — no LLM). Also scaffolds
`.claude/docs/reference/` (the compile input) with a README.

Idempotent and safe: if `domain.json` already exists it is **left untouched** —
re-running init (or re-mint) never clobbers authored content.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Optional

from harness.domain import detect

# default locations (relative to project root) for the claude plugin
_DEFAULT_MANIFEST_REL = ".claude/harness-wf-plugin/domain/domain.json"
_DEFAULT_REFERENCE_REL = ".claude/docs/reference"


def _platform_paths(platform: Optional[str]):
    """Compute (manifest_rel, reference_rel) for *platform*, relative to the
    project root. ``None`` → the legacy claude defaults (byte-identical).

    For plugin platforms (claude) the deployed root is
    ``<config_dir>/<plugin_dir_name>``; for embedded platforms (gemini/cursor/
    codex/generic) it is ``<config_dir>``. The manifest lives at
    ``<root>/domain/domain.json``; the reference docs at
    ``<config_dir>/docs/reference``.
    """
    if platform is None:
        return _DEFAULT_MANIFEST_REL, _DEFAULT_REFERENCE_REL
    # Imported lazily so seed.py keeps no hard dependency at module import time.
    from harness.adapters.profile import load_profile

    profile = load_profile(platform)
    root = profile.domain_root_rel()
    return f"{root}/domain/domain.json", f"{profile.config_dir}/docs/reference"

# conventional docs worth suggesting as references (path → first H1 label)
_REFERENCE_CANDIDATES = (
    "README.md", "CHANGELOG.md", "CONTRIBUTING.md", "ARCHITECTURE.md",
    "RELEASING.md", "docs/README.md", "docs/RELEASING.md",
    "docs/ARCHITECTURE.md",
)
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

_README = """# Reference docs

Drop the docs that describe **what this product is and where it's going** here:
PRD, product direction, business goals, key decisions, domain background.

Then run:

    harness-wf domain-compile

It distills these into the `business` section of `domain.json` (direction,
priorities, constraints, non_goals). Re-run it whenever these docs change.
"""


def _first_h1(text: str) -> str:
    m = _H1_RE.search(text or "")
    return m.group(1).strip() if m else ""


def suggest_references(project_path) -> dict:
    """Pre-suggest references from conventional docs (path → first H1). Docs
    without an H1 are skipped. Humans curate from here."""
    pp = Path(project_path)
    refs: dict = {}

    for rel in _REFERENCE_CANDIDATES:
        p = pp / rel
        if not p.exists():
            continue
        try:
            title = _first_h1(p.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        if title:
            refs[rel] = title
    return refs


def scaffold_reference_dir(reference_dir) -> bool:
    """Create the reference docs dir + README. Returns True if it created the
    README, False if it already existed."""
    d = Path(reference_dir)
    d.mkdir(parents=True, exist_ok=True)
    readme = d / "README.md"
    if readme.exists():
        return False
    readme.write_text(_README, encoding="utf-8")
    return True


def build_scaffold(stack, references) -> dict:
    """The initial domain.json: stack filled, manual slots empty, references
    suggested. `_comment` is ignored by the model (breadcrumb only)."""
    return {
        "schema_version": 1,
        "_comment": "Project-ops manifest. Fill environments/test/deploy/infra; "
                    "run `harness-wf domain-compile` to populate `business`.",
        "stack": list(stack),
        "environments": {},
        "test": {},
        "deploy": {},
        "infra": {},
        "references": dict(references),
    }


def run_domain_init(
    project_path,
    *,
    platform: Optional[str] = None,
    manifest_path: Optional[Path] = None,
    reference_dir: Optional[Path] = None,
    detect_stack_fn: Callable = detect.detect_stack,
    output_fn: Callable[[str], None] = print,
) -> Path:
    """Detect → scaffold. Returns the manifest path. Never clobbers an existing
    domain.json (preserves authored content on re-run/re-mint).

    When *platform* is given (and explicit paths are not) the default manifest
    and reference locations are computed from that platform's profile, so a
    non-claude mint writes under the right config dir. Explicit
    ``manifest_path``/``reference_dir`` always win. ``platform=None`` preserves
    the legacy claude defaults exactly."""
    pp = Path(project_path)
    manifest_rel, reference_rel = _platform_paths(platform)
    mp = Path(manifest_path) if manifest_path else pp / manifest_rel
    ref_dir = Path(reference_dir) if reference_dir else pp / reference_rel

    scaffold_reference_dir(ref_dir)

    if mp.exists():
        output_fn(f"domain.json already exists at {mp} — left untouched.")
        return mp

    stack = detect_stack_fn(pp)
    references = suggest_references(pp)
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(build_scaffold(stack, references), indent=2) + "\n", encoding="utf-8")
    output_fn(f"Scaffolded {mp}. Fill the slots; add docs to {ref_dir}, then run domain-compile.")
    return mp


def run_domain_refresh(
    project_path,
    *,
    platform: Optional[str] = None,
    manifest_path: Optional[Path] = None,
    detect_stack_fn: Callable = detect.detect_stack,
    output_fn: Callable[[str], None] = print,
) -> Path:
    """Re-detect the stack and merge it into an existing domain.json, updating
    only `stack` and leaving authored sections (environments/test/deploy/infra)
    and the compiled `business` untouched. No-op with a hint if the manifest
    doesn't exist yet — run `domain-init` first. (Mirror of `domain-compile`,
    which refreshes only `business`.)

    *platform* selects the default manifest location (see `run_domain_init`);
    an explicit ``manifest_path`` always wins. ``platform=None`` preserves the
    legacy claude default."""
    pp = Path(project_path)
    manifest_rel, _ = _platform_paths(platform)
    mp = Path(manifest_path) if manifest_path else pp / manifest_rel

    if not mp.exists():
        output_fn(f"No domain.json at {mp} — run `harness-wf domain-init` first.")
        return mp

    data = json.loads(mp.read_text(encoding="utf-8"))
    data["stack"] = list(detect_stack_fn(pp))
    mp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    output_fn(f"Refreshed stack ({len(data['stack'])} item(s)) in {mp}.")
    return mp
