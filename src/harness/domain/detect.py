"""harness.domain.detect — reliable stack detection (no code-structure inference).

Languages come from **GitHub Linguist** via the `/languages` API when an `origin`
GitHub remote exists, with a deterministic file-extension fallback offline.
Frameworks and services come from **cdxgen** (CycloneDX BOM). Every external
call (git, HTTP, npx) is injected so the pure logic is unit-tested and any
failure degrades gracefully to a partial/empty result — detection never blocks.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Callable, Optional

# extension → language (the offline fallback; Linguist is preferred when online)
_EXT_LANG = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".go": "Go", ".rs": "Rust",
    ".java": "Java", ".rb": "Ruby", ".php": "PHP", ".c": "C", ".h": "C",
    ".cpp": "C++", ".cc": "C++", ".cs": "C#", ".kt": "Kotlin", ".swift": "Swift",
    ".scala": "Scala", ".sh": "Shell", ".lua": "Lua", ".dart": "Dart",
}
_SKIP_DIRS = {".git", ".venv", "node_modules", "dist", "build", "__pycache__", ".codegraph"}
_GITHUB_RE = re.compile(r"github\.com[:/]+([^/]+/[^/]+?)(?:\.git)?/?$")


def _run(cmd, **kw):
    """Default subprocess runner (capture text, never raise on non-zero).

    Forwards optional ``cwd``/``env`` so callers can sandbox where a tool writes
    its artifacts (cdxgen drops ``bom.json`` into the working directory)."""
    return subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=kw.get("timeout", 120), cwd=kw.get("cwd"), env=kw.get("env"),
    )


# detected language → cdxgen project type (``-t``). Telling cdxgen the ecosystem
# is what turns "0 components" into a populated BOM; TS and JS share one type.
_LANG_TO_CDXGEN_TYPE = {
    "Python": "python", "JavaScript": "javascript", "TypeScript": "javascript",
    "Java": "java", "Kotlin": "java", "Scala": "java", "Go": "go", "Rust": "rust",
    "Ruby": "ruby", "PHP": "php", "C#": "csharp",
}


def _cdxgen_types(languages: list[str]) -> list[str]:
    """Map detected languages → de-duplicated cdxgen ``-t`` project types."""
    out: list[str] = []
    for lang in languages:
        t = _LANG_TO_CDXGEN_TYPE.get(lang)
        if t and t not in out:
            out.append(t)
    return out


def _http_get_json(url: str) -> Optional[dict]:
    """Default HTTP GET returning parsed JSON, or None on any failure."""
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _github_repo_slug(project_path, *, run: Callable = _run) -> Optional[str]:
    """Return "owner/repo" if origin is a GitHub remote, else None."""
    try:
        result = run(["git", "-C", str(project_path), "remote", "get-url", "origin"])
        if getattr(result, "returncode", 1) != 0:
            return None
        m = _GITHUB_RE.search((result.stdout or "").strip())
        return m.group(1) if m else None
    except Exception:
        return None


def _extension_languages(project_path) -> list[str]:
    """Offline fallback: count source files by extension → languages, desc."""
    counts: Counter = Counter()
    # os.walk with in-place pruning so skipped trees (node_modules, .venv, …)
    # are never entered — rglob would enumerate them fully before filtering.
    for _dirpath, dirnames, filenames in os.walk(project_path):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            lang = _EXT_LANG.get(Path(name).suffix.lower())
            if lang:
                counts[lang] += 1
    return [lang for lang, _ in counts.most_common()]


def detect_languages(
    project_path,
    *,
    run: Callable = _run,
    http_get: Callable[[str], Optional[dict]] = _http_get_json,
) -> list[str]:
    """Languages via GitHub Linguist (/languages API), weighted desc; offline →
    file-extension fallback."""
    slug = _github_repo_slug(project_path, run=run)
    if slug:
        data = http_get(f"https://api.github.com/repos/{slug}/languages")
        if isinstance(data, dict) and data:
            return sorted(data, key=lambda k: data[k], reverse=True)
    return _extension_languages(project_path)


def _cdxgen_bom(project_path, types: list[str], *, run: Callable = _run) -> Optional[dict]:
    """Run cdxgen and return the parsed CycloneDX BOM dict, or None on any failure.

    cdxgen's ``-o -`` stdout mode is unreliable (it logs to stdout and still
    writes a file), so we write the BOM to an explicit file inside a temp dir —
    with ``cwd`` set to that dir so cdxgen can never drop ``bom.json`` into the
    scanned repo — then read and parse the file."""
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "bom.json")
        cmd = ["npx", "--yes", "@cyclonedx/cdxgen@12", "--no-validate", "-o", out]
        for t in types:
            cmd += ["-t", t]
        # Absolute: cwd is the temp dir, so a relative path would scan the wrong place.
        cmd.append(str(Path(project_path).resolve()))
        try:
            result = run(cmd, cwd=td, env={**os.environ, "FETCH_LICENSE": "false"})
        except Exception:
            return None
        if getattr(result, "returncode", 1) != 0:
            return None
        try:
            with open(out) as f:
                bom = json.loads(f.read())
        except Exception:
            return None
    return bom if isinstance(bom, dict) else None


def detect_frameworks(
    project_path,
    *,
    run: Callable = _run,
    languages: Optional[list[str]] = None,
    bom_fn: Callable[..., Optional[dict]] = _cdxgen_bom,
) -> dict:
    """Frameworks + services via cdxgen (CycloneDX BOM). ``languages`` selects the
    cdxgen project type(s). Degrades to empty lists on any failure (cdxgen
    missing, non-zero exit, no/unparseable BOM)."""
    empty = {"frameworks": [], "services": []}
    bom = bom_fn(project_path, _cdxgen_types(languages or []), run=run)
    if not isinstance(bom, dict):
        return empty
    frameworks = [
        c["name"] for c in bom.get("components", [])
        if isinstance(c, dict) and c.get("name") and c.get("type") in ("framework", "application")
    ]
    services = [
        s["name"] for s in bom.get("services", [])
        if isinstance(s, dict) and s.get("name")
    ]
    return {"frameworks": frameworks, "services": services}


def detect_stack(
    project_path,
    *,
    run: Callable = _run,
    http_get: Callable[[str], Optional[dict]] = _http_get_json,
    frameworks_fn: Callable[..., dict] = detect_frameworks,
) -> list[str]:
    """Combined stack: languages then frameworks, de-duplicated (order-preserving)."""
    langs = detect_languages(project_path, run=run, http_get=http_get)
    frameworks = frameworks_fn(project_path, run=run, languages=langs).get("frameworks", [])
    out: list[str] = []
    for item in [*langs, *frameworks]:
        if item not in out:
            out.append(item)
    return out
