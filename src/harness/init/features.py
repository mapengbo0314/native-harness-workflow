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
}

#: Dependency map: if a feature is enabled (or absent → fail-open = enabled)
#: AND its dependency is EXPLICITLY disabled, raise FeaturesValidationError.
DEPENDENCIES: dict[str, str] = {
    "pipeline.dispatcher.gates.search_first": "services.session_memory.enabled",
    "hooks.session_end.learning_extraction": "services.session_memory.enabled",
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
