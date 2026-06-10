"""Unit tests for harness.domain.model — OpsManifest.

TDD: these tests were written before the implementation and drive it.

Covered behaviours:
- schema_version parsed; stack parsed as tuple; blank stack entries dropped.
- Blank values dropped across sections; empty list and blank string dropped,
  but a non-empty list (e.g. business.priorities=["a","b"]) kept.
- topic("deploy") → {"deploy": {...}}; topic("stack") → {"stack": [...]};
  topic("business") returns the business dict.
- topic("all") keys == the 7 topics; topic("") and topic(None) == topic("all");
  case-insensitive (topic("DEPLOY")==topic("deploy")); unknown topic → {}.
- load() from a tmp file; empty manifest (from_json("{}") and from_json(""))
  is safe (stack==(), topic("deploy")=={"deploy":{}}).
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from harness.domain.model import OpsManifest, TOPICS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FULL_DATA = {
    "schema_version": 2,
    "stack": ["Python", "", "TypeScript", "   "],
    "environments": {
        "staging": "https://staging.example.com",
        "prod": "",
    },
    "test": {
        "unit": "pytest",
        "integration": None,
    },
    "deploy": {
        "command": "make deploy",
        "notes": "",
    },
    "infra": {
        "provider": "AWS",
        "region": [],
    },
    "references": {
        "runbook": "https://wiki/runbook",
        "empty_link": {},
    },
    "business": {
        "direction": "Build the best tool",
        "priorities": ["a", "b"],
        "non_goals": "",
        "constraints": [],
    },
}


# ---------------------------------------------------------------------------
# TOPICS constant
# ---------------------------------------------------------------------------

class TestTopicsConstant:
    def test_topics_is_tuple_of_seven(self):
        assert isinstance(TOPICS, tuple)
        assert len(TOPICS) == 7

    def test_topics_contains_expected_names(self):
        expected = {"stack", "environments", "test", "deploy", "infra", "references", "business"}
        assert set(TOPICS) == expected


# ---------------------------------------------------------------------------
# OpsManifest.from_dict
# ---------------------------------------------------------------------------

class TestFromDict:
    def test_schema_version_parsed(self):
        m = OpsManifest.from_dict({"schema_version": "3"})
        assert m.schema_version == 3

    def test_schema_version_defaults_to_1(self):
        m = OpsManifest.from_dict({})
        assert m.schema_version == 1

    def test_stack_parsed_as_tuple(self):
        m = OpsManifest.from_dict({"stack": ["Python", "Go"]})
        assert isinstance(m.stack, tuple)
        assert m.stack == ("Python", "Go")

    def test_stack_blank_entries_dropped(self):
        m = OpsManifest.from_dict({"stack": ["Python", "", "   ", "Go"]})
        assert m.stack == ("Python", "Go")

    def test_stack_defaults_to_empty_tuple(self):
        m = OpsManifest.from_dict({})
        assert m.stack == ()

    def test_sections_parsed(self):
        m = OpsManifest.from_dict(FULL_DATA)
        assert m.deploy["command"] == "make deploy"
        assert m.business["direction"] == "Build the best tool"

    def test_blank_string_values_dropped(self):
        m = OpsManifest.from_dict(FULL_DATA)
        # "prod": "" should be dropped from environments
        assert "prod" not in m.environments
        assert "staging" in m.environments

    def test_none_values_dropped(self):
        m = OpsManifest.from_dict(FULL_DATA)
        # "integration": None should be dropped from test
        assert "integration" not in m.test

    def test_empty_list_values_dropped(self):
        m = OpsManifest.from_dict(FULL_DATA)
        # "region": [] should be dropped from infra
        assert "region" not in m.infra

    def test_empty_dict_values_dropped(self):
        m = OpsManifest.from_dict(FULL_DATA)
        # "empty_link": {} should be dropped from references
        assert "empty_link" not in m.references

    def test_non_empty_list_kept(self):
        m = OpsManifest.from_dict(FULL_DATA)
        # "priorities": ["a", "b"] — non-empty list must be kept
        assert m.business["priorities"] == ["a", "b"]

    def test_blank_string_in_section_dropped(self):
        m = OpsManifest.from_dict(FULL_DATA)
        # "non_goals": "" should be dropped
        assert "non_goals" not in m.business

    def test_whitespace_only_string_dropped(self):
        m = OpsManifest.from_dict({"deploy": {"cmd": "   "}})
        assert "cmd" not in m.deploy


# ---------------------------------------------------------------------------
# OpsManifest.from_json
# ---------------------------------------------------------------------------

class TestFromJson:
    def test_from_json_parses_valid_text(self):
        text = json.dumps({"schema_version": 2, "stack": ["Rust"]})
        m = OpsManifest.from_json(text)
        assert m.schema_version == 2
        assert m.stack == ("Rust",)

    def test_from_json_empty_string_is_safe(self):
        m = OpsManifest.from_json("")
        assert m.stack == ()
        assert m.deploy == {}

    def test_from_json_empty_braces(self):
        m = OpsManifest.from_json("{}")
        assert m.stack == ()
        assert m.topic("deploy") == {"deploy": {}}


# ---------------------------------------------------------------------------
# OpsManifest.load
# ---------------------------------------------------------------------------

class TestLoad:
    def test_load_from_tmp_file(self):
        data = {"schema_version": 1, "stack": ["Node"], "deploy": {"cmd": "npm run deploy"}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            tmp_path = Path(f.name)
        try:
            m = OpsManifest.load(tmp_path)
            assert m.stack == ("Node",)
            assert m.deploy["cmd"] == "npm run deploy"
        finally:
            tmp_path.unlink()


# ---------------------------------------------------------------------------
# OpsManifest.as_dict
# ---------------------------------------------------------------------------

class TestAsDict:
    def test_as_dict_has_seven_keys(self):
        m = OpsManifest()
        d = m.as_dict()
        assert set(d.keys()) == set(TOPICS)

    def test_as_dict_stack_is_list(self):
        m = OpsManifest.from_dict({"stack": ["Python"]})
        assert m.as_dict()["stack"] == ["Python"]

    def test_as_dict_defaults_are_empty(self):
        m = OpsManifest()
        d = m.as_dict()
        assert d["stack"] == []
        assert d["deploy"] == {}


# ---------------------------------------------------------------------------
# OpsManifest.topic
# ---------------------------------------------------------------------------

class TestTopic:
    def _manifest(self):
        return OpsManifest.from_dict(FULL_DATA)

    def test_topic_deploy_returns_deploy_dict(self):
        m = self._manifest()
        result = m.topic("deploy")
        assert set(result.keys()) == {"deploy"}
        assert result["deploy"]["command"] == "make deploy"

    def test_topic_stack_returns_stack_list(self):
        m = self._manifest()
        result = m.topic("stack")
        assert result == {"stack": ["Python", "TypeScript"]}

    def test_topic_business_returns_business_dict(self):
        m = self._manifest()
        result = m.topic("business")
        assert "business" in result
        assert result["business"]["priorities"] == ["a", "b"]

    def test_topic_all_has_seven_keys(self):
        m = self._manifest()
        result = m.topic("all")
        assert set(result.keys()) == set(TOPICS)

    def test_topic_empty_string_equals_all(self):
        m = self._manifest()
        assert m.topic("") == m.topic("all")

    def test_topic_none_equals_all(self):
        m = self._manifest()
        assert m.topic(None) == m.topic("all")

    def test_topic_case_insensitive(self):
        m = self._manifest()
        assert m.topic("DEPLOY") == m.topic("deploy")
        assert m.topic("Deploy") == m.topic("deploy")

    def test_topic_unknown_returns_empty_dict(self):
        m = self._manifest()
        assert m.topic("nonexistent") == {}

    def test_topic_deploy_on_empty_manifest(self):
        m = OpsManifest()
        assert m.topic("deploy") == {"deploy": {}}

    def test_topic_stack_on_empty_manifest(self):
        m = OpsManifest()
        assert m.topic("stack") == {"stack": []}
