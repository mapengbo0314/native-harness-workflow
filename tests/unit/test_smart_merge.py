import pytest
import json
import yaml
from harness.minting_engine import merge_markdown, merge_structured

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
