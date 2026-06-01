import pytest
import json
import yaml
from harness.init.minting_engine import merge_markdown, merge_structured

def test_merge_markdown_sections():
    """
    Test that markdown sections are merged correctly.
    New sections should be added, and existing sections should be updated.
    """
    old_md = "# Header 1\nOld content\n# Header 2\nOld Header 2 content"
    new_md = "# Header 1\nNew content\n# Header 3\nNew Header 3 content"
    merged = merge_markdown(old_md, new_md)
    assert "# Header 1\nNew content" in merged
    assert "Old content" not in merged  # Verify old content was replaced
    assert "# Header 2\nOld Header 2 content" in merged
    assert "# Header 3\nNew Header 3 content" in merged

def test_merge_structured_json():
    """
    Test deep merge of JSON objects.
    """
    old_json = '{"a": 1, "b": {"c": 2}}'
    new_json = '{"b": {"d": 3}, "e": 4}'
    merged = merge_structured(old_json, new_json, format="json")
    data = json.loads(merged)
    assert data["a"] == 1
    assert data["b"]["c"] == 2
    assert data["b"]["d"] == 3
    assert data["e"] == 4

def test_merge_structured_yaml():
    """
    Test deep merge of YAML objects.
    """
    old_yaml = "a: 1\nb:\n  c: 2"
    new_yaml = "b:\n  d: 3\ne: 4"
    merged = merge_structured(old_yaml, new_yaml, format='yaml')
    data = yaml.safe_load(merged)
    assert data["a"] == 1
    assert data["b"]["c"] == 2
    assert data["b"]["d"] == 3
    assert data["e"] == 4

def test_merge_structured_list_union():
    """
    Test that lists are unioned (merged without duplicates) in structured data.
    """
    old_json = '{"list": [1, 2], "nested": {"l": ["a", "b"]}}'
    new_json = '{"list": [2, 3], "nested": {"l": ["b", "c"]}}'
    merged = merge_structured(old_json, new_json, format="json")
    data = json.loads(merged)
    
    assert set(data["list"]) == {1, 2, 3}
    assert set(data["nested"]["l"]) == {"a", "b", "c"}
    assert len(data["list"]) == 3
    assert len(data["nested"]["l"]) == 3

def test_perform_smart_merge(tmp_path, monkeypatch):
    """
    Test that perform_smart_merge correctly walks a directory and merges files.
    """
    from harness.init.minting_engine import perform_smart_merge
    
    existing_dir = tmp_path / "existing"
    staged_dir = tmp_path / "staged"
    
    existing_dir.mkdir()
    staged_dir.mkdir()
    
    # 1. Markdown file merge
    (existing_dir / "README.md").write_text("# Title\nOld content\n# Old Section\nOld text")
    (staged_dir / "README.md").write_text("# Title\nNew content\n# New Section\nNew text")
    
    # 2. JSON file merge
    (existing_dir / "config.json").write_text('{"a": 1, "b": 2}')
    (staged_dir / "config.json").write_text('{"b": 3, "c": 4}')
    
    # 3. New file in staged (should remain as is)
    (staged_dir / "new_file.py").write_text("print('new')")
    
    # 4. Code file conflict (headless mode auto-overwrite)
    (existing_dir / "app.py").write_text("print('old')")
    (staged_dir / "app.py").write_text("print('new')")
    
    # Mock headless mode
    monkeypatch.setenv("HARNESS_HEADLESS", "1")
    perform_smart_merge(existing_dir, staged_dir)
    
    # Verify README.md
    readme_content = (staged_dir / "README.md").read_text()
    assert "# Title\nNew content" in readme_content
    assert "# Old Section\nOld text" in readme_content
    assert "# New Section\nNew text" in readme_content
    
    # Verify config.json
    config_data = json.loads((staged_dir / "config.json").read_text())
    assert config_data["a"] == 1
    assert config_data["b"] == 3
    assert config_data["c"] == 4
    
    # Verify new_file.py
    assert (staged_dir / "new_file.py").read_text() == "print('new')"
    
    # Verify app.py (auto-overwritten)
    assert (staged_dir / "app.py").read_text() == "print('new')"


def test_merge_structured_named_list_deduplicates_by_name():
    """Reinstalling with a renamed plugin dir must not produce duplicate marketplace entries."""
    old_json = json.dumps({"plugins": [
        {"name": "orchestrator-plugin", "source": "./harness-wr-plugin", "version": "0.1.0"}
    ]})
    new_json = json.dumps({"plugins": [
        {"name": "orchestrator-plugin", "source": "./harness-wf-plugin", "version": "0.1.0"}
    ]})
    merged = json.loads(merge_structured(old_json, new_json, format="json"))
    assert len(merged["plugins"]) == 1, "duplicate plugin names must be collapsed to one"
    assert merged["plugins"][0]["source"] == "./harness-wf-plugin", "new entry must win"


def test_merge_structured_named_list_update_wins():
    """When names collide the incoming (new) entry replaces the existing one."""
    old_json = json.dumps({"plugins": [
        {"name": "orchestrator-plugin", "source": "./old-dir", "version": "0.1.0"},
        {"name": "other-plugin", "source": "./other", "version": "1.0.0"},
    ]})
    new_json = json.dumps({"plugins": [
        {"name": "orchestrator-plugin", "source": "./new-dir", "version": "0.2.0"},
    ]})
    merged = json.loads(merge_structured(old_json, new_json, format="json"))
    assert len(merged["plugins"]) == 2, "unrelated plugin must be preserved"
    orchestrator = next(p for p in merged["plugins"] if p["name"] == "orchestrator-plugin")
    assert orchestrator["source"] == "./new-dir"
    assert orchestrator["version"] == "0.2.0"


def test_merge_structured_plain_list_still_unions():
    """Plain lists (no 'name' key) must still union without duplicates."""
    old_json = '{"tags": ["a", "b"]}'
    new_json = '{"tags": ["b", "c"]}'
    merged = json.loads(merge_structured(old_json, new_json, format="json"))
    assert sorted(merged["tags"]) == ["a", "b", "c"]
