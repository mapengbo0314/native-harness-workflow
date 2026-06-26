"""Phase 0 (ECC feature port): tool-plane feature-toggle compiler.

Operators edit ``<plugin_root>/features.yaml``; this module validates it and
compiles it to ``<plugin_root>/features.json`` (sorted keys, 2-space indent).
The deployed hooks then read ONLY the JSON — no YAML import in the deployed
plane (boilerplate/).

Public API
----------
compile_features(plugin_root: Path) -> Path | None
    Compile features.yaml -> features.json.  Returns the JSON path, or None
    if features.yaml is missing (no-op).

FeaturesValidationError
    Raised (and no JSON written) on type violations or dependency violations.
"""
from __future__ import annotations

import copy
import json
import warnings
from pathlib import Path
from typing import Any, Optional

import yaml  # PyYAML — available in the tool plane


# ---------------------------------------------------------------------------
# Schema  (leaves = bool; dict nodes = nested schema)
# ---------------------------------------------------------------------------

#: KNOWN_KEYS declares the valid feature tree.  Leaves must be booleans in
#: the YAML.  Dict nodes may have further sub-keys *or* be used as "enabled"
#: flag objects (e.g. ``services.session_memory: {enabled: true}``).
KNOWN_KEYS: dict[str, Any] = {
    "rules_packs": {
        "enabled": bool,
        "languages": dict,  # per-language bool leaves freely allowed under here
    },
    "services": {
        "session_memory": {
            "enabled": bool,
        },
    },
    "hooks": {
        "session_end": {
            "learning_extraction": bool,
        },
        # Per-hook listeners.  prompt_classifier/pre_tool_use are pipeline- and
        # security-critical: their flags are schema-valid but intentionally NOT
        # early-exited at runtime (disabling belongs to settings.json
        # registration, not a hot-path guard).  post_tool_use and
        # notify_compression are safe to early-exit on their flag.
        "prompt_classifier": bool,
        "pre_tool_use": bool,
        "post_tool_use": bool,
        "notify_compression": bool,
    },
    "agents": {
        # Persona toggles.  A disabled persona degrades to @generalist
        # (hook_common.effective_agent).  generalist is the always-on fallback.
        "generalist": bool,
        "debugger": bool,
        "planner": bool,
        "implementer": bool,
        "verifier": bool,
        "reviewer": bool,
        "adversary": bool,
    },
    "mcp": {
        # MCP server toggles.  compile_mcp_config drops disabled servers from
        # the active .mcp.json (catalog mcp_servers.json is the source of truth).
        "domain": bool,
        "codegraph": bool,
    },
    "pipeline": {
        "dispatcher": {
            "gates": {
                "search_first": bool,
                "adversary_exit": bool,
            },
        },
    },
    "skills": {
        "continuous-learning": bool,
        "search-first": bool,
        "adversary-pipeline": bool,
    },
    "branches": {
        # Plan A–E dispatch branches.  Disabling a branch makes the
        # dispatcher degrade to plan_e (answer-only); plan_e is the
        # always-on terminal fallback.
        "plan_a_bugs": bool,
        "plan_b_discovery": bool,
        "plan_c_readonly": bool,
        "plan_d_execution": bool,
        "plan_e_answer": bool,
    },
}

#: Dependency map: if a feature is enabled (or absent → fail-open = enabled)
#: AND its dependency is EXPLICITLY disabled, raise FeaturesValidationError.
DEPENDENCIES: dict[str, str] = {
    "pipeline.dispatcher.gates.search_first": "services.session_memory.enabled",
    "hooks.session_end.learning_extraction": "services.session_memory.enabled",
    # Cross-class edges (Increment 4): a Plan branch requires its agent persona.
    # Disabling the agent cascades the branch off (which then degrades to E at
    # dispatch via hook_common.effective_branch).  One dependency per feature.
    "branches.plan_a_bugs": "agents.debugger",
    "branches.plan_b_discovery": "agents.planner",
    "branches.plan_d_execution": "agents.implementer",
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class FeaturesValidationError(ValueError):
    """Raised when features.yaml violates type constraints or dependency rules."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_nested(data: dict, dotted: str, default=None):
    """Traverse *data* using a dotted key; return *default* if any key is missing."""
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def _validate_tree(data: Any, schema: Any, path: str) -> None:
    """Recursively validate *data* against *schema*.

    Unknown keys emit a UserWarning (R3 — still compiles).
    Wrong type (non-bool where bool expected) raises FeaturesValidationError.
    """
    if schema is bool:
        # Leaf: must be a Python bool
        if not isinstance(data, bool):
            raise FeaturesValidationError(
                f"Expected bool at '{path}', got {type(data).__name__!r}: {data!r}"
            )
        return

    if schema is dict:
        # Free-form dict (e.g. rules_packs.languages) — no further validation
        return

    if isinstance(schema, dict):
        if not isinstance(data, dict):
            raise FeaturesValidationError(
                f"Expected mapping at '{path}', got {type(data).__name__!r}"
            )
        for key, value in data.items():
            child_path = f"{path}.{key}" if path else key
            if key not in schema:
                warnings.warn(
                    f"features.yaml: unknown key '{child_path}'",
                    UserWarning,
                    stacklevel=4,
                )
                # Still compile — unknown key is just a warning
            else:
                _validate_tree(value, schema[key], child_path)
        return

    # Fallback: no specific schema constraint
    return


def _check_dependencies(data: dict) -> None:
    """Enforce DEPENDENCIES rules.

    If a feature resolves to enabled (or is absent → fail-open = enabled)
    AND its declared dependency is *explicitly* ``false`` or
    ``{"enabled": false}``, raise FeaturesValidationError.
    """
    for feature_key, dep_key in DEPENDENCIES.items():
        # Determine if the feature is enabled
        raw_feature = _get_nested(data, feature_key, default=None)
        if raw_feature is False:
            # feature explicitly disabled → no dependency problem
            continue
        # raw_feature is True, absent (None), or a dict without enabled=False → enabled

        # Determine if the dependency is *explicitly* disabled
        raw_dep = _get_nested(data, dep_key, default=None)
        dep_disabled = (
            raw_dep is False
            or (isinstance(raw_dep, dict) and raw_dep.get("enabled") is False)
        )
        if dep_disabled:
            raise FeaturesValidationError(
                f"Feature '{feature_key}' is enabled but its dependency "
                f"'{dep_key}' is explicitly disabled."
            )


# ---------------------------------------------------------------------------
# Cascade-aware toggling
# ---------------------------------------------------------------------------

def _set_nested(data: dict, dotted: str, value: bool) -> None:
    """Set *value* at *dotted* path in *data*, creating intermediate dicts."""
    parts = dotted.split(".")
    node = data
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


def _cascade_disable(data: dict, disabled_key: str) -> None:
    """Disable every feature that (transitively) requires *disabled_key*."""
    stack = [disabled_key]
    seen: set[str] = set()
    while stack:
        dep = stack.pop()
        for feature_key, required in DEPENDENCIES.items():
            if required == dep and feature_key not in seen:
                seen.add(feature_key)
                _set_nested(data, feature_key, False)
                stack.append(feature_key)


def _cascade_enable(data: dict, enabled_key: str) -> None:
    """Enable whatever *enabled_key* (transitively) depends on."""
    key = enabled_key
    seen: set[str] = set()
    while key in DEPENDENCIES and key not in seen:
        seen.add(key)
        dep = DEPENDENCIES[key]
        _set_nested(data, dep, True)
        key = dep


def apply_toggle(data: dict, dotted_key: str, value: bool) -> dict:
    """Return a NEW feature map with *dotted_key* set to *value*, cascaded.

    Maintains dependency validity so a toggle never lands in a state that
    ``_check_dependencies`` would reject:

    - Disabling a key also disables every feature that requires it
      (transitive reverse edges).
    - Enabling a key also enables whatever it depends on (transitive
      forward edges).

    The input is never mutated (immutability rule); a deep copy is returned.
    """
    result = copy.deepcopy(data)
    _set_nested(result, dotted_key, value)
    if value:
        _cascade_enable(result, dotted_key)
    else:
        _cascade_disable(result, dotted_key)
    return result


# ---------------------------------------------------------------------------
# Key enumeration, validation, and status rendering
# ---------------------------------------------------------------------------

def _iter_known_leaves(schema: Any = None, prefix: str = ""):
    """Yield ``(dotted_path, is_freeform)`` for every leaf in ``KNOWN_KEYS``.

    A ``bool`` leaf yields ``(path, False)``; a free-form ``dict`` marker
    (e.g. ``rules_packs.languages``) yields ``(path, True)``.
    """
    if schema is None:
        schema = KNOWN_KEYS
    for key, val in schema.items():
        path = f"{prefix}.{key}" if prefix else key
        if val is bool:
            yield path, False
        elif val is dict:
            yield path, True
        elif isinstance(val, dict):
            yield from _iter_known_leaves(val, path)


def known_feature_keys() -> tuple[set[str], set[str]]:
    """Return ``(leaf_paths, freeform_prefixes)`` from ``KNOWN_KEYS``."""
    leaves: set[str] = set()
    freeform: set[str] = set()
    for path, is_freeform in _iter_known_leaves():
        (freeform if is_freeform else leaves).add(path)
    return leaves, freeform


def valid_feature_key(key: str) -> bool:
    """True if *key* is a known toggle leaf or a free-form subtree member."""
    leaves, freeform = known_feature_keys()
    if key in leaves:
        return True
    return any(key.startswith(prefix + ".") for prefix in freeform)


def _resolve(data: dict, dotted: str, default: bool = True) -> bool:
    """Resolve a toggle value from *data* with feature_enabled semantics."""
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    if isinstance(node, bool):
        return node
    if isinstance(node, dict):
        enabled = node.get("enabled")
        return enabled if isinstance(enabled, bool) else default
    return default


def format_features_status(data: dict) -> str:
    """Render every known toggle leaf as ``[x]``/``[ ] <path>`` (fail-open)."""
    leaves, _ = known_feature_keys()
    lines = []
    for path in sorted(leaves):
        mark = "[x]" if _resolve(data, path, default=True) else "[ ]"
        lines.append(f"  {mark} {path}")
    return "\n".join(lines)


def build_checklist(data: dict) -> list[tuple[str, bool]]:
    """Return sorted ``(key, is_on)`` rows for every known toggle (fail-open).

    The pure view-model behind the interactive ``features toggle`` UI.
    """
    leaves, _ = known_feature_keys()
    return [(path, _resolve(data, path, default=True)) for path in sorted(leaves)]


# ---------------------------------------------------------------------------
# MCP server toggles
# ---------------------------------------------------------------------------

def filter_mcp_servers(mcp_config: dict, features: dict) -> dict:
    """Return a copy of *mcp_config* with disabled servers removed (pure).

    A server ``name`` is dropped when ``mcp.<name>`` resolves to False in
    *features*.  Absent flags fail-open (server kept).  The input is not
    mutated.
    """
    servers = mcp_config.get("mcpServers", {})
    if not isinstance(servers, dict):
        return dict(mcp_config)
    kept = {
        name: cfg
        for name, cfg in servers.items()
        if _resolve(features, f"mcp.{name}", default=True)
    }
    return {**mcp_config, "mcpServers": kept}


def compile_mcp_config(plugin_root: Path) -> Optional[Path]:
    """Generate ``.mcp.json`` from the ``mcp_servers.json`` catalog + flags.

    The catalog (``<plugin_root>/mcp_servers.json``) is the non-destructive
    source of truth; this writes the active ``<plugin_root>/.mcp.json`` with
    disabled servers removed.  Returns the active path, or ``None`` when no
    catalog is present (no-op).
    """
    plugin_root = Path(plugin_root)
    catalog_path = plugin_root / "mcp_servers.json"
    if not catalog_path.exists():
        return None

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    features: dict = {}
    features_json = plugin_root / "features.json"
    if features_json.exists():
        try:
            features = json.loads(features_json.read_text(encoding="utf-8"))
        except Exception:
            features = {}

    active = filter_mcp_servers(catalog, features)
    active_path = plugin_root / ".mcp.json"
    active_path.write_text(
        json.dumps(active, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return active_path


def toggle_at(data: dict, index: int) -> dict:
    """Flip the toggle at checklist row *index* (cascade-aware).

    Returns a new dict (immutability); raises ``IndexError`` if out of range.
    """
    rows = build_checklist(data)
    key, is_on = rows[index]
    return apply_toggle(data, key, not is_on)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compile_features(plugin_root: Path) -> Optional[Path]:
    """Read ``<plugin_root>/features.yaml``, validate, and write ``features.json``.

    Returns the JSON path on success.  Returns ``None`` if ``features.yaml``
    does not exist (no-op).  Raises ``FeaturesValidationError`` on schema or
    dependency violations (no JSON written in that case).
    """
    plugin_root = Path(plugin_root)
    yaml_path = plugin_root / "features.yaml"
    json_path = plugin_root / "features.json"

    if not yaml_path.exists():
        return None

    raw = yaml_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}

    # --- Guard: root must be a mapping ---
    if not isinstance(data, dict):
        raise FeaturesValidationError(
            f"features.yaml root must be a mapping, got {type(data).__name__!r}"
        )

    # --- Validate schema ---
    _validate_tree(data, KNOWN_KEYS, "")

    # --- Validate dependencies ---
    _check_dependencies(data)

    # --- Write JSON (sorted keys, 2-space indent, trailing newline) ---
    json_path.write_text(
        json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return json_path
