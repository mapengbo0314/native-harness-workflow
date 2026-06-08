"""harness.domain.compiler — `harness-wf domain-compile`.

Read the human-authored docs in `.claude/docs/reference/`, make ONE isolated LLM
call (the developer's local `claude`/`gemini` CLI — no API key) to distill a few
fixed, decision-relevant business fields, and merge them into the `business`
section of the plugin's `domain.json` (preserving all other sections).

The `business` section is a point-in-time digest, not live — re-run when the
reference docs change. The LLM only summarizes human-authored docs; it never
infers from code. Input is bounded so a large docs folder can't overflow the call.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable, Optional

_DOC_EXT = {".md", ".txt", ".rst", ".markdown"}
_PER_DOC_CAP = 20_000      # chars per doc
_TOTAL_CAP = 120_000       # chars across all docs (then truncated)
BUSINESS_FIELDS = ("direction", "priorities", "constraints", "non_goals")

_PROMPT = """You are distilling a product's reference docs into a tiny, durable
"business" summary that helps an AI coding agent make judgment calls aligned with
the product direction.

Read the documents below and return ONLY a JSON object with these keys:
- "direction": one sentence on where the product is headed / what it optimizes for.
- "priorities": a short list (<=4) of what matters most, highest first.
- "constraints": a short list (<=4) of hard business/product constraints to respect.
- "non_goals": a short list (<=4) of things explicitly out of scope.

Keep every entry to one short line. Omit a key the docs don't support. Return
JSON only — no prose, no code fences.

=== DOCUMENTS ===
{docs}
=== END DOCUMENTS ===
"""


def read_reference_docs(reference_dir) -> str:
    """Concatenate reference docs (md/txt/…) under *reference_dir*, each prefixed
    with its relative path. Skips the scaffold README. Bounded per-doc and in
    total. Returns "" if the dir is absent/empty."""
    d = Path(reference_dir)
    if not d.exists():
        return ""
    parts: list[str] = []
    total = 0
    for p in sorted(d.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in _DOC_EXT:
            continue
        rel = p.relative_to(d).as_posix()
        if rel == "README.md":
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")[:_PER_DOC_CAP]
        except OSError:
            continue
        chunk = f"## {rel}\n{text.strip()}"
        if total + len(chunk) > _TOTAL_CAP:
            parts.append(chunk[: _TOTAL_CAP - total] + "\n…(truncated)")
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n\n".join(parts)


def _parse_business(raw: str) -> dict:
    """Extract the JSON object from an LLM response; keep only known, non-empty
    BUSINESS_FIELDS."""
    if not raw:
        return {}
    s, e = raw.find("{"), raw.rfind("}")
    if s == -1 or e <= s:
        return {}
    try:
        data = json.loads(raw[s:e + 1])
    except (json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict = {}
    for k in BUSINESS_FIELDS:
        v = data.get(k)
        if v in ("", None, [], {}):
            continue
        if isinstance(v, str) and not v.strip():
            continue
        out[k] = v
    return out


def compile_business(docs_text: str, *, query_llm_fn: Callable[[str], str]) -> dict:
    """Distill the fixed business fields from docs text. {} for empty docs
    (without calling the LLM) or unparseable responses."""
    if not (docs_text or "").strip():
        return {}
    return _parse_business(query_llm_fn(_PROMPT.format(docs=docs_text)))


def _default_query_llm_fn() -> Optional[Callable[[str], str]]:
    """Wrap llm_client.query_llm (local CLI). Returns None if no CLI is on PATH
    (so the caller degrades gracefully instead of crashing)."""
    cli = "claude" if shutil.which("claude") else ("gemini" if shutil.which("gemini") else None)
    if cli is None:
        return None
    from harness.runtime.llm_client import query_llm
    return lambda prompt: query_llm(prompt, cli)


def run_domain_compile(
    project_path,
    *,
    manifest_path: Path,
    reference_dir: Path,
    query_llm_fn: Optional[Callable[[str], str]] = None,
    output_fn: Callable[[str], None] = print,
) -> Path:
    """Read reference docs → compile business → merge into domain.json.

    No-op (no LLM call, no business write) when there are no reference docs."""
    mp = Path(manifest_path)
    docs_text = read_reference_docs(reference_dir)
    if not docs_text:
        output_fn(f"No reference docs in {reference_dir}. Add PRD/product docs, then re-run domain-compile.")
        return mp

    if query_llm_fn is None:
        query_llm_fn = _default_query_llm_fn()
        if query_llm_fn is None:
            output_fn("No `claude`/`gemini` CLI found on PATH — skipping business compile.")
            return mp

    business = compile_business(docs_text, query_llm_fn=query_llm_fn)

    data = {}
    if mp.exists():
        try:
            data = json.loads(mp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    data.setdefault("schema_version", 1)
    data["business"] = business
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    output_fn(f"Compiled business ({len(business)} field(s)) into {mp}")
    return mp
