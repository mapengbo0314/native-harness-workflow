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

# conventional docs worth suggesting as references (path → first H1 label)
_REFERENCE_CANDIDATES = (
    "README.md", "CHANGELOG.md", "CONTRIBUTING.md", "ARCHITECTURE.md",
    "RELEASING.md", "docs/README.md", "docs/RELEASING.md",
    "docs/ARCHITECTURE.md", "docs/domain/CONTEXT.md",
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
    manifest_path: Optional[Path] = None,
    reference_dir: Optional[Path] = None,
    detect_stack_fn: Callable = detect.detect_stack,
    output_fn: Callable[[str], None] = print,
) -> Path:
    """Detect → scaffold. Returns the manifest path. Never clobbers an existing
    domain.json (preserves authored content on re-run/re-mint)."""
    pp = Path(project_path)
    mp = Path(manifest_path) if manifest_path else pp / _DEFAULT_MANIFEST_REL
    ref_dir = Path(reference_dir) if reference_dir else pp / _DEFAULT_REFERENCE_REL

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
