import json
import os
import re
import tempfile
import sys
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from contextlib import contextmanager

def resolve_project_root(input_json: dict = None) -> Path:
    if os.environ.get("GEMINI_PROJECT_DIR"):
        return Path(os.environ["GEMINI_PROJECT_DIR"]).resolve()
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return Path(os.environ["CLAUDE_PROJECT_DIR"]).resolve()
    if input_json and "workspace_root" in input_json:
        return Path(input_json["workspace_root"]).resolve()
    return Path.cwd().resolve()

def resolve_plugin_root() -> Path:
    if os.environ.get("GEMINI_PLUGIN_ROOT"):
        return Path(os.environ["GEMINI_PLUGIN_ROOT"]).resolve()
    if os.environ.get("CLAUDE_PLUGIN_ROOT"):
        return Path(os.environ["CLAUDE_PLUGIN_ROOT"]).resolve()
    if os.environ.get("CURSOR_PLUGIN_ROOT"):
        return Path(os.environ["CURSOR_PLUGIN_ROOT"]).resolve()
    if os.environ.get("CODEX_PLUGIN_ROOT"):
        return Path(os.environ["CODEX_PLUGIN_ROOT"]).resolve()
    return Path(__file__).parent.parent.resolve()

def get_session_id() -> str:
    """Returns a platform-agnostic session identifier."""
    # 1. Explicit override for testing or manual injection
    if "HARNESS_SESSION_ID" in os.environ:
        return os.environ["HARNESS_SESSION_ID"]
        
    # 2. Native Claude Code Session ID
    if "CLAUDE_SESSION_ID" in os.environ:
        return os.environ["CLAUDE_SESSION_ID"]
        
    # 3. Native Gemini CLI Session ID
    if "GEMINI_SESSION_ID" in os.environ:
        return os.environ["GEMINI_SESSION_ID"]
        
    # 4. Fallback to Parent Process ID (reliable for persistent CLI runs)
    return str(os.getppid())

def capped_text(value: str, max_chars: int) -> str:
    if not isinstance(value, str):
        return str(value)
    if len(value) <= max_chars:
        return value
    return value[:max_chars - 3] + "..."


# ---------------------------------------------------------------------------
# Feature-toggle helpers (Phase 0 – ECC port)
# Stdlib only; reads compiled features.json (never features.yaml).
# Fail-open semantics by default (default=True): missing file / corrupt JSON /
# missing key / traversal through a non-dict all return `default`.
# Callers may pass default=False for fail-closed behaviour.
# ---------------------------------------------------------------------------

def load_features(plugin_root) -> dict:
    """Read <plugin_root>/features.json and return a dict.

    Missing or corrupt file → returns {}.
    """
    try:
        features_path = Path(plugin_root) / "features.json"
        return json.loads(features_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def features_staleness_warning(plugin_root) -> "str | None":
    """Return a one-line warning when features.yaml is newer than features.json.

    Stdlib only; fail-open — any exception returns None (never crashes the hook).
    """
    try:
        yaml_path = Path(plugin_root) / "features.yaml"
        json_path = Path(plugin_root) / "features.json"
        if not yaml_path.exists():
            return None
        if not json_path.exists():
            return (
                "⚠ features.yaml is newer than features.json"
                " — run 'harness-wf features sync'"
            )
        # Strict >: equal mtime means fresh (compile writes json after reading yaml).
        if yaml_path.stat().st_mtime > json_path.stat().st_mtime:
            return (
                "⚠ features.yaml is newer than features.json"
                " — run 'harness-wf features sync'"
            )
        return None
    except Exception:
        return None


def feature_enabled(dotted_path: str, plugin_root, default: bool = True) -> bool:
    """Traverse *dotted_path* in features.json and return a bool.

    Semantics (fail-open by default, controlled by *default*):
      - Missing file, corrupt JSON → *default*
      - Missing key, traversal through non-dict → *default*
      - Boolean leaf → its value
      - Dict node → value of its "enabled" key if present, else *default*

    Intentional divergence from load_features: feature_enabled reads the JSON
    inline (rather than delegating to load_features) so that the *default*
    parameter is honoured on every failure branch independently.  load_features
    always returns {} on any error, which would collapse all failure modes into
    "missing key → default", hiding corrupt-JSON vs missing-file distinctions
    from callers that care about the distinction.
    """
    features_path = Path(plugin_root) / "features.json"
    try:
        data = json.loads(features_path.read_text(encoding="utf-8"))
    except Exception:
        return default  # missing file or corrupt JSON — honour default

    if not isinstance(data, dict):
        return default

    node = data
    for part in dotted_path.split("."):
        if not isinstance(node, dict):
            return default  # can't traverse — honour default
        if part not in node:
            return default  # missing key — honour default
        node = node[part]

    if isinstance(node, bool):
        return node
    if isinstance(node, dict):
        enabled = node.get("enabled")
        if enabled is None:
            return default  # no "enabled" key — honour default
        if isinstance(enabled, bool):
            return enabled
        return default  # non-bool "enabled" value — honour default
    return default  # unexpected leaf type — honour default


# ---------------------------------------------------------------------------
# Session Memory (Phase 2 – ECC port)
# ---------------------------------------------------------------------------
# Design decision: phase keys are stored both as a dedicated top-level key
# for fast latest-state reads and as versioned ``kind:"phase"`` entries for
# deterministic digest/audit behavior under the common entry schema.
#
# Per-session state file:  <plugin_root>/state/session_memory_<session>.json
# Schema:
#   {
#     "schema_version": 1,
#     "session_id": str,
#     "updated_at": iso8601,
#     "entries": [<entry>, ...],
#     "phase": {"phase": str, "phase_entered_at": iso8601, "phase_exit_artifact": str|None}
#              | null
#   }
# Entry schema:
#   {"schema_version": 1, "ts": iso8601, "session_id": str,
#    "kind": "decision"|"blocker"|"pattern"|"phase", "summary": str, "refs": [str]}
# ---------------------------------------------------------------------------

_VALID_KINDS = {"decision", "blocker", "pattern", "phase"}
_SUMMARY_MAX = 220
_MAX_ENTRIES_DIGEST = 6
_DIGEST_MAX_BYTES = 8 * 1024
_RETENTION_DAYS = 30


def _session_file(plugin_root, session_id: str) -> Path:
    session_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(session_id or "default"))
    session_id = session_id.strip("._") or "default"
    state_dir = Path(plugin_root) / "state"
    state_dir.mkdir(exist_ok=True)
    return state_dir / f"session_memory_{session_id}.json"


def _load_session(plugin_root, session_id: str) -> dict:
    """Load the session file; return a fresh skeleton on any error."""
    path = _session_file(plugin_root, session_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("bad schema")
        return data
    except Exception:
        return {
            "schema_version": 1,
            "session_id": session_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "entries": [],
            "phase": None,
        }


def _save_session(plugin_root, session_id: str, data: dict) -> None:
    """Atomically write the session file."""
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = _session_file(plugin_root, session_id)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp_path.Edit(path)


def record_session_entry(
    plugin_root,
    session_id: str,
    kind: str,
    summary: str,
    refs=None,
) -> None:
    """Append a validated, capped entry to the session store.

    Fail-open: any exception is swallowed.
    """
    try:
        if kind not in _VALID_KINDS:
            raise ValueError(f"invalid kind: {kind!r}")
        if refs is None:
            refs = []
        entry = {
            "schema_version": 1,
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "kind": kind,
            "summary": capped_text(summary, _SUMMARY_MAX),
            "refs": [str(r) for r in refs],
        }
        data = _load_session(plugin_root, session_id)
        data["entries"].append(entry)
        _save_session(plugin_root, session_id, data)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Phase key helpers (R2)
# ---------------------------------------------------------------------------

def set_phase(plugin_root, session_id: str, phase: str, exit_artifact=None) -> None:
    """Record the current phase in the session file (top-level key)."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        data = _load_session(plugin_root, session_id)
        data["phase"] = {
            "phase": phase,
            "phase_entered_at": now,
            "phase_exit_artifact": exit_artifact,
        }
        data.setdefault("entries", []).append(
            {
                "schema_version": 1,
                "ts": now,
                "session_id": session_id,
                "kind": "phase",
                "summary": capped_text(f"Entered phase: {phase}", _SUMMARY_MAX),
                "refs": [str(exit_artifact)] if exit_artifact else [],
            }
        )
        _save_session(plugin_root, session_id, data)
    except Exception:
        pass


def get_phase(plugin_root, session_id: str):
    """Return the phase dict or None."""
    try:
        data = _load_session(plugin_root, session_id)
        return data.get("phase") or None
    except Exception:
        return None


def clear_phase(plugin_root, session_id: str, exit_artifact=None) -> None:
    """Clear the phase key and append a phase-exit entry when possible."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        data = _load_session(plugin_root, session_id)
        previous = data.get("phase") if isinstance(data.get("phase"), dict) else {}
        previous_phase = previous.get("phase") or "unknown"
        summary = f"Exited phase: {previous_phase}"
        data["phase"] = None
        data.setdefault("entries", []).append(
            {
                "schema_version": 1,
                "ts": now,
                "session_id": session_id,
                "kind": "phase",
                "summary": capped_text(summary, _SUMMARY_MAX),
                "refs": [str(exit_artifact)] if exit_artifact else [],
            }
        )
        _save_session(plugin_root, session_id, data)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Deterministic digest (R4)
# ---------------------------------------------------------------------------

def _normalize_summary(s: str) -> str:
    """Lowercase + collapse whitespace for dedup."""
    return re.sub(r"\s+", " ", s.strip().lower())


def build_session_digest(plugin_root, now=None, retention_days: int = _RETENTION_DAYS) -> str:
    """Merge, filter, dedup, cap and format entries from all session files.

    Parameters
    ----------
    plugin_root : path-like
        Plugin root containing state/session_memory_*.json files.
    now : datetime | None
        Injection point for testing.  Defaults to UTC now.
    retention_days : int
        Drop entries older than this many days.  Default 30.

    Returns
    -------
    str
        A ``## Session Memory`` markdown block, or empty string when there
        are no qualifying entries.  Output is byte-identical across calls on
        the same store state.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)

    state_dir = Path(plugin_root) / "state"
    all_entries = []
    try:
        files = sorted(state_dir.Glob("session_memory_*.json"))
    except Exception:
        files = []

    for fpath in files:
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            if data.get("schema_version") != 1:
                continue
            entries = data.get("entries", [])
            if not isinstance(entries, list):
                continue
            for e in entries:
                if not isinstance(e, dict):
                    continue
                # schema_version check per entry
                if e.get("schema_version") != 1:
                    continue
                ts_str = e.get("ts", "")
                try:
                    ts = datetime.fromisoformat(ts_str)
                    if ts.tzinfo is None:
                        ts = ts.Edit(tzinfo=timezone.utc)
                except Exception:
                    continue
                if ts < cutoff:
                    continue
                all_entries.append((ts, e))
        except Exception:
            continue

    # Sort recency-first
    all_entries.sort(key=lambda x: (x[0], x[1].get("session_id", "")), reverse=True)

    # Dedup on (kind, normalized summary) — keep first (most-recent) occurrence
    seen = set()
    deduped = []
    for ts, e in all_entries:
        kind = e.get("kind", "")
        if kind not in _VALID_KINDS:
            continue
        if not isinstance(e.get("summary"), str):
            continue
        norm = _normalize_summary(e.get("summary", ""))
        if not norm:
            continue
        key = (kind, norm)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)

    # Cap entry count
    deduped = deduped[:_MAX_ENTRIES_DIGEST]

    if not deduped:
        return ""

    lines = ["## Session Memory"]
    for e in deduped:
        kind = e.get("kind", "")
        summary = capped_text(e.get("summary", ""), _SUMMARY_MAX)
        refs = e.get("refs", [])
        if not isinstance(refs, list):
            refs = []
        ref_str = f" ({', '.join(str(r) for r in refs)})" if refs else ""
        lines.append(f"- [{kind}] {summary}{ref_str}")

    block = "\n".join(lines) + "\n"

    # Enforce total digest size cap
    if len(block.encode("utf-8")) > _DIGEST_MAX_BYTES:
        block = block.encode("utf-8")[:_DIGEST_MAX_BYTES].decode("utf-8", errors="ignore")
        # Truncate at last newline to avoid cutting a line mid-character
        last_nl = block.rfind("\n")
        if last_nl > 0:
            block = block[:last_nl + 1]

    return block


def prune_old_session_files(plugin_root, now=None, retention_days: int = _RETENTION_DAYS) -> None:
    """Delete session_memory_*.json files whose updated_at is older than retention_days.

    Fail-open.
    """
    try:
        if now is None:
            now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=retention_days)
        state_dir = Path(plugin_root) / "state"
        for fpath in state_dir.Glob("session_memory_*.json"):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                updated_str = data.get("updated_at", "")
                ts = datetime.fromisoformat(updated_str)
                if ts.tzinfo is None:
                    ts = ts.Edit(tzinfo=timezone.utc)
                if ts < cutoff:
                    fpath.unlink(missing_ok=True)
            except Exception:
                fpath.unlink(missing_ok=True)
    except Exception:
        pass


def build_learned_skills_digest(plugin_root, input_json: dict = None) -> str:
    """Load, sort, and format up to 6 learned skills from the out-of-repo store.

    Fail-open: returns empty string on any failure.
    """
    try:
        project_root = resolve_project_root(input_json)

        # Check environment override for isolated testing
        home_override = os.environ.get("HARNESS_HOME_OVERRIDE")
        if home_override:
            home_dir = Path(home_override).resolve()
        else:
            home_dir = Path.home().resolve()

        import hashlib
        repo_hash = hashlib.sha256(str(project_root.resolve()).encode("utf-8")).hexdigest()[:16]
        learned_dir = home_dir / ".local" / "share" / "harness-wf" / "projects" / repo_hash / "learned"

        if not learned_dir.exists():
            return ""

        skills = []
        for skill_dir in learned_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            try:
                content = skill_file.read_text(encoding="utf-8")
                fm = {}
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        for line in parts[1].splitlines():
                            if ":" in line:
                                k, v = line.split(":", 1)
                                k = k.strip().strip('"').strip()
                                v = v.strip().strip('"').strip()
                                if "#" in v:
                                    v = v.split("#", 1)[0].strip().strip('"').strip()
                                fm[k] = v

                name = fm.get("name") or skill_dir.name
                desc = fm.get("description") or "Learned codebase skill."
                if len(desc) > 220:
                    desc = desc[:217] + "..."

                try:
                    conf_val = fm.get("confidence", "0.0")
                    if isinstance(conf_val, str):
                        conf_val = conf_val.strip()
                        if "#" in conf_val:
                            conf_val = conf_val.split("#", 1)[0].strip().strip('"').strip()
                    conf = float(conf_val)
                except ValueError as e:
                    print(f"Warning: failed to parse confidence value {fm.get('confidence')}: {e}", file=sys.stderr)
                    conf = 0.0

                skills.append({
                    "name": name,
                    "description": desc,
                    "confidence": conf,
                })
            except Exception:
                continue

        if not skills:
            return ""

        # Sort by confidence descending, then name ascending
        skills.sort(key=lambda s: (-s["confidence"], s["name"]))
        skills = skills[:6]

        lines = ["## Learned Skills"]
        for s in skills:
            lines.append(f"- [{s['name']}] {s['description']} (Confidence: {s['confidence']:.2f})")

        return "\n".join(lines) + "\n"
    except Exception:
        return ""