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
