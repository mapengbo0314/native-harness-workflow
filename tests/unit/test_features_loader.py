"""Phase 0 (ECC feature port): tool-plane compiler + loader parity tests.

TDD — these tests are written BEFORE src/harness/init/features.py exists.
They pin:
  - YAML -> JSON compilation (nesting preserved, comments stripped)
  - Unknown key: warns but still compiles
  - Wrong type (non-bool where bool expected): raises FeaturesValidationError,
    no JSON written
  - Dependency violation: raises FeaturesValidationError naming both keys
  - Loader parity: compiled JSON read by deployed feature_enabled gives YAML values
"""
from __future__ import annotations

import importlib.util
import json
import sys
import warnings
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: load the deployed hook module via importlib (stdlib-only module,
# never importable as a package — mirror the pattern in test_feature_toggles.py)
# ---------------------------------------------------------------------------
HOOKS_DIR = (
    Path(__file__).parent.parent.parent
    / "src/harness/templates/boilerplate/hooks"
)


@pytest.fixture(scope="module")
def hook_common():
    spec = importlib.util.spec_from_file_location(
        "hook_common_loader_parity", HOOKS_DIR / "hook_common.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Import the tool-plane compiler (regular package import is fine here)
# ---------------------------------------------------------------------------
from harness.init.features import (
    FeaturesValidationError,
    apply_toggle,
    compile_features,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_yaml(root: Path, content: str) -> None:
    (root / "features.yaml").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# YAML -> JSON compilation
# ---------------------------------------------------------------------------


def test_compile_roundtrip_preserves_nesting(tmp_path):
    yaml_text = """\
# operator comment — must be stripped
pipeline:
  dispatcher:
    gates:
      search_first: true
      adversary_exit: false
services:
  session_memory:
    enabled: true
"""
    write_yaml(tmp_path, yaml_text)
    out = compile_features(tmp_path)
    assert out is not None
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["pipeline"]["dispatcher"]["gates"]["search_first"] is True
    assert data["pipeline"]["dispatcher"]["gates"]["adversary_exit"] is False
    assert data["services"]["session_memory"]["enabled"] is True
    # Comments stripped: valid JSON (already implied by json.loads above)


def test_compile_sorted_keys(tmp_path):
    write_yaml(tmp_path, "services:\n  session_memory:\n    enabled: true\npipeline:\n  dispatcher:\n    gates:\n      search_first: false\n")
    out = compile_features(tmp_path)
    text = out.read_text()
    # sorted keys: "pipeline" < "services"
    assert text.index('"pipeline"') < text.index('"services"')


def test_compile_missing_yaml_returns_none(tmp_path):
    result = compile_features(tmp_path)
    assert result is None


def test_compile_writes_json_file(tmp_path):
    write_yaml(tmp_path, "rules_packs:\n  enabled: true\n")
    out = compile_features(tmp_path)
    assert out == tmp_path / "features.json"


# ---------------------------------------------------------------------------
# Unknown key: warns but still compiles
# ---------------------------------------------------------------------------


def test_unknown_key_warns_but_compiles(tmp_path):
    write_yaml(tmp_path, "totally_unknown_key: true\n")
    with pytest.warns(UserWarning, match="unknown key"):
        out = compile_features(tmp_path)
    assert out is not None and out.exists()


# ---------------------------------------------------------------------------
# Wrong type: raises FeaturesValidationError, no JSON written
# ---------------------------------------------------------------------------


def test_wrong_type_raises_and_no_json(tmp_path):
    # rules_packs.enabled expects bool; give it a string
    write_yaml(tmp_path, "rules_packs:\n  enabled: 'yes'\n")
    with pytest.raises(FeaturesValidationError):
        compile_features(tmp_path)
    assert not (tmp_path / "features.json").exists()


def test_non_dict_root_raises_validation_error(tmp_path):
    """YAML root must be a mapping; a list root must raise FeaturesValidationError."""
    write_yaml(tmp_path, "- item1\n- item2\n")
    with pytest.raises(FeaturesValidationError, match="root must be a mapping"):
        compile_features(tmp_path)
    assert not (tmp_path / "features.json").exists()
    # Also test with a scalar root
    write_yaml(tmp_path, "just_a_string\n")
    with pytest.raises(FeaturesValidationError, match="root must be a mapping"):
        compile_features(tmp_path)


# ---------------------------------------------------------------------------
# Dependency validation
# ---------------------------------------------------------------------------


def test_dependency_violation_raises_naming_both_keys(tmp_path):
    # search_first enabled (default), session_memory explicitly disabled
    yaml_text = """\
pipeline:
  dispatcher:
    gates:
      search_first: true
services:
  session_memory:
    enabled: false
"""
    write_yaml(tmp_path, yaml_text)
    with pytest.raises(FeaturesValidationError) as exc_info:
        compile_features(tmp_path)
    msg = str(exc_info.value)
    assert "pipeline.dispatcher.gates.search_first" in msg
    assert "services.session_memory.enabled" in msg


def test_dependency_ok_when_dep_enabled(tmp_path):
    yaml_text = """\
pipeline:
  dispatcher:
    gates:
      search_first: true
hooks:
  session_end:
    learning_extraction: true
services:
  session_memory:
    enabled: true
"""
    write_yaml(tmp_path, yaml_text)
    out = compile_features(tmp_path)
    assert out is not None


def test_dependency_ok_when_both_features_disabled(tmp_path):
    # Both dependent features explicitly disabled; dep also disabled — no violation
    yaml_text = """\
pipeline:
  dispatcher:
    gates:
      search_first: false
hooks:
  session_end:
    learning_extraction: false
services:
  session_memory:
    enabled: false
"""
    write_yaml(tmp_path, yaml_text)
    out = compile_features(tmp_path)
    assert out is not None


# ---------------------------------------------------------------------------
# Loader parity: compiled JSON read by deployed feature_enabled
# ---------------------------------------------------------------------------


def test_loader_parity_bool_leaf(tmp_path, hook_common):
    write_yaml(tmp_path, "pipeline:\n  dispatcher:\n    gates:\n      search_first: false\n")
    compile_features(tmp_path)
    result = hook_common.feature_enabled(
        "pipeline.dispatcher.gates.search_first", tmp_path
    )
    assert result is False


def test_loader_parity_dict_node_enabled_false(tmp_path, hook_common):
    # Disable session_memory AND all features that depend on it so compile doesn't raise.
    yaml_text = """\
pipeline:
  dispatcher:
    gates:
      search_first: false
hooks:
  session_end:
    learning_extraction: false
services:
  session_memory:
    enabled: false
"""
    write_yaml(tmp_path, yaml_text)
    compile_features(tmp_path)
    result = hook_common.feature_enabled("services.session_memory", tmp_path)
    assert result is False


def test_loader_parity_missing_key_fail_open(tmp_path, hook_common):
    write_yaml(tmp_path, "rules_packs:\n  enabled: true\n")
    compile_features(tmp_path)
    # key not in compiled JSON -> fail-open
    result = hook_common.feature_enabled(
        "pipeline.dispatcher.gates.search_first", tmp_path
    )
    assert result is True


def test_known_keys_disjoint_from_codex_tool_mapping(tmp_path):
    """No KNOWN_KEYS flattened leaf path must collide with codex tool_mapping keys.

    The codex adapter maps tool names (Read, Write, Bash, etc.) — if a feature
    key ever matched one of those names the YAML parser could misinterpret the
    toggle surface during template rendering.
    """
    import json as _json
    from pathlib import Path as _Path
    from harness.init.features import KNOWN_KEYS

    profiles_path = (
        _Path(__file__).parent.parent.parent
        / "src/harness/adapters/platform_profiles.json"
    )
    profiles = _json.loads(profiles_path.read_text(encoding="utf-8"))
    codex_tool_keys = set(profiles.get("codex", {}).get("tool_mappings", {}).keys())

    def _flatten(node, prefix=""):
        parts = set()
        if isinstance(node, dict):
            for k, v in node.items():
                sub = f"{prefix}.{k}" if prefix else k
                parts.add(k)          # segment
                parts.add(sub)        # dotted path
                parts.update(_flatten(v, sub))
        return parts

    known_segments = _flatten(KNOWN_KEYS)
    collision = known_segments & codex_tool_keys
    assert not collision, (
        f"KNOWN_KEYS segments collide with codex tool_mapping keys: {collision}"
    )


# ---------------------------------------------------------------------------
# Plan A–E branch toggles: schema coverage
# ---------------------------------------------------------------------------


def test_branches_block_compiles_and_round_trips(tmp_path):
    yaml_text = """\
branches:
  plan_a_bugs: true
  plan_b_discovery: false
  plan_c_readonly: true
  plan_d_execution: false
  plan_e_answer: true
"""
    write_yaml(tmp_path, yaml_text)
    out = compile_features(tmp_path)
    assert out is not None
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["branches"]["plan_b_discovery"] is False
    assert data["branches"]["plan_d_execution"] is False


def test_branches_wrong_type_raises(tmp_path):
    write_yaml(tmp_path, 'branches:\n  plan_a_bugs: "yes"\n')
    with pytest.raises(FeaturesValidationError):
        compile_features(tmp_path)


# ---------------------------------------------------------------------------
# Cascade-aware toggling: apply_toggle(data, dotted_key, value) -> new dict
# ---------------------------------------------------------------------------


def _baseline() -> dict:
    """All dependency-linked features on (matches features.yaml defaults)."""
    return {
        "services": {"session_memory": {"enabled": True}},
        "hooks": {"session_end": {"learning_extraction": True}},
        "pipeline": {"dispatcher": {"gates": {"search_first": True, "adversary_exit": True}}},
        "rules_packs": {"enabled": True},
    }


def test_apply_toggle_disable_dependency_cascades_to_dependents():
    # Turning OFF a dependency turns OFF every feature that requires it.
    result = apply_toggle(_baseline(), "services.session_memory.enabled", False)
    assert result["services"]["session_memory"]["enabled"] is False
    assert result["pipeline"]["dispatcher"]["gates"]["search_first"] is False
    assert result["hooks"]["session_end"]["learning_extraction"] is False


def test_apply_toggle_enable_feature_pulls_in_dependency():
    # Turning ON a feature turns ON whatever it depends on.
    start = {
        "services": {"session_memory": {"enabled": False}},
        "pipeline": {"dispatcher": {"gates": {"search_first": False}}},
    }
    result = apply_toggle(start, "pipeline.dispatcher.gates.search_first", True)
    assert result["pipeline"]["dispatcher"]["gates"]["search_first"] is True
    assert result["services"]["session_memory"]["enabled"] is True


def test_apply_toggle_independent_key_leaves_others_untouched():
    result = apply_toggle(_baseline(), "rules_packs.enabled", False)
    assert result["rules_packs"]["enabled"] is False
    # No dependency edge touches session_memory.
    assert result["services"]["session_memory"]["enabled"] is True


def test_apply_toggle_returns_new_object_without_mutating_input():
    data = _baseline()
    result = apply_toggle(data, "services.session_memory.enabled", False)
    # Original is unchanged (immutability rule).
    assert data["services"]["session_memory"]["enabled"] is True
    assert result is not data


# ---------------------------------------------------------------------------
# Increment 4: breadth — agents / hooks / mcp schema + cross-class cascade
# ---------------------------------------------------------------------------


def test_agents_hooks_mcp_blocks_compile_and_round_trip(tmp_path):
    yaml_text = """\
agents:
  generalist: true
  debugger: true
  planner: true
  implementer: true
hooks:
  post_tool_use: false
  notify_compression: true
mcp:
  domain: true
  codegraph: false
"""
    write_yaml(tmp_path, yaml_text)
    out = compile_features(tmp_path)
    assert out is not None
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["agents"]["debugger"] is True
    assert data["hooks"]["post_tool_use"] is False
    assert data["mcp"]["codegraph"] is False


def test_apply_toggle_disable_agent_cascades_to_its_branch():
    # Cross-class edge: branches.plan_a_bugs requires agents.debugger.
    start = {
        "agents": {"debugger": True},
        "branches": {"plan_a_bugs": True},
    }
    result = apply_toggle(start, "agents.debugger", False)
    assert result["agents"]["debugger"] is False
    assert result["branches"]["plan_a_bugs"] is False


def test_cross_class_dependency_violation_raises_naming_both(tmp_path):
    yaml_text = """\
branches:
  plan_a_bugs: true
agents:
  debugger: false
"""
    write_yaml(tmp_path, yaml_text)
    with pytest.raises(FeaturesValidationError) as exc_info:
        compile_features(tmp_path)
    msg = str(exc_info.value)
    assert "branches.plan_a_bugs" in msg
    assert "agents.debugger" in msg
