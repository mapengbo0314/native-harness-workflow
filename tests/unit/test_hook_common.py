import pytest
from pathlib import Path
from harness.templates.boilerplate.hooks.hook_common import (
    resolve_project_root,
    resolve_plugin_root,
    resolve_state_path,
    append_event,
    capped_text
)

def test_resolve_project_root_with_input():
    input_json = {"workspace_root": "/fake/path"}
    root = resolve_project_root(input_json)
    assert str(root) == "/fake/path"

def test_resolve_project_root_without_input():
    root = resolve_project_root()
    assert str(root) == str(Path.cwd())

def test_append_event():
    state = {"events": []}
    new_state = append_event(state, {"type": "test"})
    assert len(new_state["events"]) == 1
    assert new_state["events"][0]["type"] == "test"

def test_capped_text():
    assert capped_text("short", 10) == "short"
    assert capped_text("this is a very long text", 10) == "this is..."
    assert capped_text(123, 10) == "123"
