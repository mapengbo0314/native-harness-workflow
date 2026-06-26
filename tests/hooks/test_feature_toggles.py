"""Phase 0 (ECC feature port): deployed-plane feature-toggle loader.

`load_features` / `feature_enabled` live in hook_common.py and read the
COMPILED features.json (operators edit features.yaml; the tool plane compiles).
Semantics under test:
  - fail-open: missing file, missing key, malformed JSON => enabled
  - dotted-path traversal (`pipeline.dispatcher.gates.search_first`)
  - a dict node is enabled unless its "enabled" key is False
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import pytest

HOOKS_DIR = (
    Path(__file__).parent.parent.parent
    / "src/harness/templates/boilerplate/hooks"
)


@pytest.fixture(scope="module")
def hook_common():
    spec = importlib.util.spec_from_file_location(
        "hook_common_under_test", HOOKS_DIR / "hook_common.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def plugin_root(tmp_path):
    return tmp_path


def write_features(root: Path, data: dict) -> None:
    (root / "features.json").write_text(json.dumps(data))


# ---------------------------------------------------------------------------
# fail-open defaults
# ---------------------------------------------------------------------------

def test_no_features_file_means_enabled(hook_common, plugin_root):
    assert hook_common.feature_enabled("anything.at.all", plugin_root) is True


def test_missing_key_means_enabled(hook_common, plugin_root):
    write_features(plugin_root, {"services": {}})
    assert hook_common.feature_enabled(
        "pipeline.dispatcher.gates.search_first", plugin_root
    ) is True


def test_malformed_json_means_enabled(hook_common, plugin_root):
    (plugin_root / "features.json").write_text("{not json!!")
    assert hook_common.feature_enabled("services.session_memory", plugin_root) is True


# ---------------------------------------------------------------------------
# dotted-path lookup
# ---------------------------------------------------------------------------

def test_disabled_leaf_returns_false(hook_common, plugin_root):
    write_features(
        plugin_root,
        {"pipeline": {"dispatcher": {"gates": {"search_first": False}}}},
    )
    assert hook_common.feature_enabled(
        "pipeline.dispatcher.gates.search_first", plugin_root
    ) is False


def test_enabled_leaf_returns_true(hook_common, plugin_root):
    write_features(
        plugin_root,
        {"pipeline": {"dispatcher": {"gates": {"search_first": True}}}},
    )
    assert hook_common.feature_enabled(
        "pipeline.dispatcher.gates.search_first", plugin_root
    ) is True


def test_dict_node_with_enabled_false(hook_common, plugin_root):
    write_features(
        plugin_root, {"services": {"session_memory": {"enabled": False}}}
    )
    assert hook_common.feature_enabled("services.session_memory", plugin_root) is False


def test_dict_node_without_enabled_key_is_enabled(hook_common, plugin_root):
    write_features(
        plugin_root, {"services": {"session_memory": {"other": 1}}}
    )
    assert hook_common.feature_enabled("services.session_memory", plugin_root) is True


def test_traversal_through_non_dict_means_enabled(hook_common, plugin_root):
    # Intermediate node is a scalar — cannot traverse; fail open.
    write_features(plugin_root, {"pipeline": True})
    assert hook_common.feature_enabled(
        "pipeline.dispatcher.gates.search_first", plugin_root
    ) is True


# ---------------------------------------------------------------------------
# load_features
# ---------------------------------------------------------------------------

def test_load_features_returns_dict(hook_common, plugin_root):
    write_features(plugin_root, {"a": {"b": False}})
    assert hook_common.load_features(plugin_root) == {"a": {"b": False}}


def test_load_features_missing_file_returns_empty(hook_common, plugin_root):
    assert hook_common.load_features(plugin_root) == {}


# ---------------------------------------------------------------------------
# default= parameter is respected for every fail-open branch (Finding 1)
# ---------------------------------------------------------------------------

def test_default_false_missing_file(hook_common, plugin_root):
    """Missing features.json with default=False must return False, not True."""
    assert hook_common.feature_enabled("missing.key", plugin_root, default=False) is False


def test_default_false_missing_key(hook_common, plugin_root):
    """Key absent in existing features.json with default=False must return False."""
    write_features(plugin_root, {"services": {}})
    assert hook_common.feature_enabled("missing.key", plugin_root, default=False) is False


def test_default_false_malformed_json(hook_common, plugin_root):
    """Malformed JSON with default=False must return False."""
    (plugin_root / "features.json").write_text("{not json!!")
    assert hook_common.feature_enabled("anything", plugin_root, default=False) is False


def test_default_false_non_dict_traversal(hook_common, plugin_root):
    """Non-dict intermediate node with default=False must return False."""
    write_features(plugin_root, {"pipeline": True})
    assert (
        hook_common.feature_enabled(
            "pipeline.dispatcher.gates.search_first", plugin_root, default=False
        )
        is False
    )


def test_default_false_dict_node_without_enabled(hook_common, plugin_root):
    """Dict node with no 'enabled' key and default=False must return False."""
    write_features(plugin_root, {"services": {"session_memory": {"other": 1}}})
    assert (
        hook_common.feature_enabled("services.session_memory", plugin_root, default=False)
        is False
    )


def test_default_unchanged_for_explicit_bool_leaf(hook_common, plugin_root):
    """Explicit bool leaf must always win regardless of default."""
    write_features(plugin_root, {"pipeline": {"dispatcher": {"gates": {"search_first": False}}}})
    # Even with default=True, explicit False must be returned.
    assert (
        hook_common.feature_enabled(
            "pipeline.dispatcher.gates.search_first", plugin_root, default=True
        )
        is False
    )


# ---------------------------------------------------------------------------
# Phase 0b: staleness guard (features_staleness_warning)
# Tests load the pure function via the module-scoped hook_common fixture.
# ---------------------------------------------------------------------------

def test_staleness_warning_yaml_newer_than_json(hook_common, plugin_root):
    """features.yaml newer than features.json -> warning string returned."""
    import os
    yaml_path = plugin_root / "features.yaml"
    json_path = plugin_root / "features.json"
    json_path.write_text("{}")
    yaml_path.write_text("rules_packs:\n  enabled: true\n")
    t = 1_000_000.0
    os.utime(json_path, (t, t))
    os.utime(yaml_path, (t + 10, t + 10))
    warning = hook_common.features_staleness_warning(plugin_root)
    assert warning is not None
    assert "features.yaml" in warning
    assert "features sync" in warning


def test_staleness_no_warning_json_newer(hook_common, plugin_root):
    """features.json newer than features.yaml -> None returned."""
    import os
    yaml_path = plugin_root / "features.yaml"
    json_path = plugin_root / "features.json"
    yaml_path.write_text("rules_packs:\n  enabled: true\n")
    json_path.write_text("{}")
    t = 1_000_000.0
    os.utime(yaml_path, (t, t))
    os.utime(json_path, (t + 10, t + 10))
    assert hook_common.features_staleness_warning(plugin_root) is None


def test_staleness_no_warning_mtime_equal(hook_common, plugin_root):
    """features.yaml mtime == features.json mtime -> None (strict > means equal is fresh)."""
    import os
    yaml_path = plugin_root / "features.yaml"
    json_path = plugin_root / "features.json"
    yaml_path.write_text("rules_packs:\n  enabled: true\n")
    json_path.write_text("{}")
    t = 1_000_000.0
    os.utime(yaml_path, (t, t))
    os.utime(json_path, (t, t))
    assert hook_common.features_staleness_warning(plugin_root) is None


def test_staleness_no_yaml_returns_none(hook_common, plugin_root):
    """No features.yaml -> None (nothing to be stale)."""
    assert hook_common.features_staleness_warning(plugin_root) is None


def test_staleness_yaml_present_json_missing_returns_warning(hook_common, plugin_root):
    """features.yaml exists but features.json absent -> warning."""
    (plugin_root / "features.yaml").write_text("rules_packs:\n  enabled: true\n")
    warning = hook_common.features_staleness_warning(plugin_root)
    assert warning is not None
    assert "features.yaml" in warning


# ---------------------------------------------------------------------------
# Phase 0b: compile_features accepts the package template (Task 4)
# ---------------------------------------------------------------------------

def test_template_features_yaml_compiles_and_all_keys_readable(plugin_root):
    """The boilerplate features.yaml must compile without error and expose all
    five design keys via feature_enabled (fail-open default=True is fine here
    since all values in the template are true)."""
    import importlib.util as _ilu
    import shutil

    # Locate the template
    template = (
        Path(__file__).parent.parent.parent
        / "src/harness/templates/boilerplate/features.yaml"
    )
    assert template.exists(), f"Template not found: {template}"

    # Copy template into plugin_root and compile
    shutil.copy(template, plugin_root / "features.yaml")

    from harness.init.features import compile_features, FeaturesValidationError
    result = compile_features(plugin_root)
    assert result is not None
    assert (plugin_root / "features.json").exists()

    # Load hook_common from the deployed plane and assert all design keys readable
    spec = _ilu.spec_from_file_location(
        "hook_common_template_test",
        Path(__file__).parent.parent.parent
        / "src/harness/templates/boilerplate/hooks/hook_common.py",
    )
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)

    design_keys = [
        "rules_packs.enabled",
        "services.session_memory.enabled",
        "hooks.session_end.learning_extraction",
        "pipeline.dispatcher.gates.search_first",
        "pipeline.dispatcher.gates.adversary_exit",
        "skills.continuous-learning",
        "skills.search-first",
        "skills.adversary-pipeline",
    ]
    for key in design_keys:
        val = mod.feature_enabled(key, plugin_root)
        assert val is True, f"Expected True for {key!r}, got {val!r}"


# ---------------------------------------------------------------------------
# Plan A–E branch toggles: effective_branch consumer
# ---------------------------------------------------------------------------


def test_effective_branch_passthrough_when_no_features_file(hook_common, plugin_root):
    # Fail-open: absent flags keep every branch active (backward compatible).
    assert hook_common.effective_branch("B", plugin_root) == "B"
    assert hook_common.effective_branch("D", plugin_root) == "D"


def test_effective_branch_passthrough_when_flag_enabled(hook_common, plugin_root):
    write_features(plugin_root, {"branches": {"plan_b_discovery": True}})
    assert hook_common.effective_branch("B", plugin_root) == "B"


def test_effective_branch_degrades_to_E_when_disabled(hook_common, plugin_root):
    write_features(plugin_root, {"branches": {"plan_d_execution": False}})
    assert hook_common.effective_branch("D", plugin_root) == "E"


def test_effective_branch_E_is_never_degraded(hook_common, plugin_root):
    write_features(plugin_root, {"branches": {"plan_e_answer": False}})
    assert hook_common.effective_branch("E", plugin_root) == "E"


def test_effective_branch_unknown_branch_passthrough(hook_common, plugin_root):
    write_features(plugin_root, {"branches": {"plan_a_bugs": False}})
    assert hook_common.effective_branch("Z", plugin_root) == "Z"
