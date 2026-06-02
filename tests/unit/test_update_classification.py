"""A1 — ownership classification rules (pure, no I/O).

Verifies the ownership boundary: which deployed plugin paths the harness owns,
their class (generated/customizable/derived), producer, and upstream source,
plus that pollution and user files are NOT owned.
"""
import pytest

from harness.update.classification import (
    classify,
    is_excluded,
    Ownership,
)


# --- exclusion (pollution + secrets + self) ---------------------------------

@pytest.mark.parametrize("relpath", [
    "state/campaign_state.json",
    "logs/run.log",
    ".venv/bin/python",
    ".deepeval/cache",
    "src/__pycache__/dispatcher.cpython-311.pyc",
    "hooks/__pycache__/x.pyc",
    "harness.db",
    "uv.lock",
    ".env.telemetry-harness",
    ".harness-meta.json",
    ".harness-update-journal.json",
])
def test_excluded_paths_are_not_owned(relpath):
    assert is_excluded(relpath) is True
    assert classify(relpath) is None


# --- runtime_copy (generated) -----------------------------------------------

def test_runtime_dispatcher_maps_to_runtime_source():
    o = classify("src/dispatcher.py")
    assert isinstance(o, Ownership)
    assert o.cls == "generated"
    assert o.producer == "runtime_copy"
    assert o.source_rel == "runtime/dispatcher.py"


def test_runtime_profile_maps_to_adapters_source():
    o = classify("src/profile.py")
    assert o.producer == "runtime_copy"
    assert o.source_rel == "adapters/profile.py"


def test_emitted_platform_adapter_has_no_source():
    o = classify("src/platform_adapter.py")
    assert o.cls == "generated"
    assert o.producer == "emitted"
    assert o.source_rel is None


# --- customizable (3-way mergeable) -----------------------------------------

def test_skill_md_is_customizable_from_boilerplate():
    o = classify("skills/diagnose/SKILL.md")
    assert o.cls == "customizable"
    assert o.producer == "template"
    assert o.source_rel == "templates/boilerplate/skills/diagnose/SKILL.md"


def test_agent_md_is_customizable():
    o = classify("agents/implementer.md")
    assert o.cls == "customizable"
    assert o.source_rel == "templates/boilerplate/agents/implementer.md"


# --- derived (regenerated from .md) -----------------------------------------

@pytest.mark.parametrize("relpath", ["agents.json", "rules.json"])
def test_json_projections_are_derived_with_no_source(relpath):
    o = classify(relpath)
    assert o.cls == "derived"
    assert o.producer == "export"
    assert o.source_rel is None


# --- generated infra --------------------------------------------------------

def test_hooks_json_is_generated_from_boilerplate():
    o = classify("hooks/hooks.json")
    assert o.cls == "generated"
    assert o.source_rel == "templates/boilerplate/hooks/hooks.json"


def test_plugin_manifest_is_generated_emitted():
    o = classify(".claude-plugin/plugin.json")
    assert o.cls == "generated"
    assert o.producer == "emitted"
    assert o.source_rel is None


# --- plugin-root static harness config files (B0 relocation) ---------------

def test_agent_json_is_generated_from_boilerplate():
    """agent.json (singular, static) relocated into plugin is generated from boilerplate."""
    o = classify("agent.json")
    assert o is not None
    assert o.cls == "generated"
    assert o.producer == "template"
    assert o.source_rel == "templates/boilerplate/agent.json"


def test_skills_json_is_generated_from_boilerplate():
    """skills.json relocated into plugin is generated from boilerplate."""
    o = classify("skills.json")
    assert o is not None
    assert o.cls == "generated"
    assert o.producer == "template"
    assert o.source_rel == "templates/boilerplate/skills.json"


def test_agents_json_plural_is_still_derived():
    """agents.json (plural, derived) must NOT be confused with agent.json (singular, static)."""
    o = classify("agents.json")
    assert o is not None
    assert o.cls == "derived"
    assert o.producer == "export"
    assert o.source_rel is None


# --- user / unknown files stay invisible ------------------------------------

@pytest.mark.parametrize("relpath", [
    "settings.json",
    "settings.local.json",
    "my_custom_skill/SKILL.md",
    "docs/my-notes.md",
])
def test_unknown_user_paths_are_not_owned(relpath):
    # Not excluded as pollution, but also not a harness producer-path -> None.
    assert classify(relpath) is None
