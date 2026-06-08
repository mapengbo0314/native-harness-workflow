"""Unit tests for harness.domain.server — domain_ops MCP tool.

TDD: tests written before implementation.

Covered behaviours:
- tool_domain_ops: single topic / "all" / blank==all / unknown=={} / empty manifest safe.
- find_manifest_path: env override (exists → path; missing → None) and ancestor walk.
- load_manifest: missing → empty OpsManifest; reads a real file correctly.
- FastMCP registration: domain_ops tool is registered in mcp._tool_manager.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from harness.domain.model import OpsManifest, TOPICS
from harness.domain.server import (
    find_manifest_path,
    load_manifest,
    tool_domain_ops,
    mcp,
)


# ---------------------------------------------------------------------------
# tool_domain_ops — pure unit
# ---------------------------------------------------------------------------

class TestToolDomainOps:
    def _manifest(self):
        return OpsManifest.from_dict({
            "stack": ["Python"],
            "deploy": {"command": "make deploy"},
            "business": {"direction": "Ship it", "priorities": ["speed"]},
        })

    def test_single_topic_deploy(self):
        m = self._manifest()
        result = tool_domain_ops("deploy", manifest=m)
        assert result == {"deploy": {"command": "make deploy"}}

    def test_single_topic_stack(self):
        m = self._manifest()
        result = tool_domain_ops("stack", manifest=m)
        assert result == {"stack": ["Python"]}

    def test_single_topic_business(self):
        m = self._manifest()
        result = tool_domain_ops("business", manifest=m)
        assert "business" in result
        assert result["business"]["priorities"] == ["speed"]

    def test_all_has_seven_keys(self):
        m = self._manifest()
        result = tool_domain_ops("all", manifest=m)
        assert set(result.keys()) == set(TOPICS)

    def test_blank_equals_all(self):
        m = self._manifest()
        assert tool_domain_ops("", manifest=m) == tool_domain_ops("all", manifest=m)

    def test_unknown_topic_returns_empty(self):
        m = self._manifest()
        assert tool_domain_ops("nonexistent", manifest=m) == {}

    def test_case_insensitive(self):
        m = self._manifest()
        assert tool_domain_ops("DEPLOY", manifest=m) == tool_domain_ops("deploy", manifest=m)

    def test_empty_manifest_safe(self):
        m = OpsManifest()
        result = tool_domain_ops("deploy", manifest=m)
        assert result == {"deploy": {}}

    def test_empty_manifest_all_safe(self):
        m = OpsManifest()
        result = tool_domain_ops("all", manifest=m)
        assert set(result.keys()) == set(TOPICS)


# ---------------------------------------------------------------------------
# find_manifest_path
# ---------------------------------------------------------------------------

class TestFindManifestPath:
    def test_env_override_existing_file(self, tmp_path, monkeypatch):
        """DOMAIN_JSON_PATH set to an existing file → that path returned."""
        p = tmp_path / "domain.json"
        p.write_text("{}")
        monkeypatch.setenv("DOMAIN_JSON_PATH", str(p))
        result = find_manifest_path()
        assert result == p

    def test_env_override_missing_file_returns_none(self, monkeypatch):
        """DOMAIN_JSON_PATH set to a non-existent file → None."""
        monkeypatch.setenv("DOMAIN_JSON_PATH", "/no/such/path/domain.json")
        result = find_manifest_path()
        assert result is None

    def test_ancestor_walk_finds_file(self, tmp_path, monkeypatch):
        """domain.json in ancestor dir is found by walking up from start."""
        monkeypatch.delenv("DOMAIN_JSON_PATH", raising=False)
        manifest = tmp_path / "domain.json"
        manifest.write_text("{}")
        # start from a nested subdir
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        result = find_manifest_path(start=nested)
        assert result == manifest

    def test_ancestor_walk_no_file_returns_none(self, tmp_path, monkeypatch):
        """No domain.json anywhere in the tree → None."""
        monkeypatch.delenv("DOMAIN_JSON_PATH", raising=False)
        # use a totally isolated tmp dir with no domain.json
        isolated = tmp_path / "isolated"
        isolated.mkdir()
        result = find_manifest_path(start=isolated)
        assert result is None

    def test_start_dir_itself_found(self, tmp_path, monkeypatch):
        """domain.json in start dir itself is found."""
        monkeypatch.delenv("DOMAIN_JSON_PATH", raising=False)
        manifest = tmp_path / "domain.json"
        manifest.write_text("{}")
        result = find_manifest_path(start=tmp_path)
        assert result == manifest


# ---------------------------------------------------------------------------
# load_manifest
# ---------------------------------------------------------------------------

class TestLoadManifest:
    def test_missing_path_returns_empty(self):
        """load_manifest(path=None) with no manifest on disk → empty OpsManifest."""
        m = load_manifest(path=Path("/no/such/domain.json"))
        assert isinstance(m, OpsManifest)
        assert m.stack == ()
        assert m.deploy == {}

    def test_reads_real_file(self, tmp_path):
        """load_manifest(path=<real file>) parses correctly."""
        data = {"stack": ["Go"], "deploy": {"cmd": "go build ./..."}}
        p = tmp_path / "domain.json"
        p.write_text(json.dumps(data))
        m = load_manifest(path=p)
        assert m.stack == ("Go",)
        assert m.deploy["cmd"] == "go build ./..."


# ---------------------------------------------------------------------------
# FastMCP registration
# ---------------------------------------------------------------------------

class TestFastMCPRegistration:
    def test_domain_ops_tool_registered(self):
        """The domain_ops tool must be registered in the FastMCP instance."""
        tool_names = {t.name for t in mcp._tool_manager.list_tools()}
        assert "domain_ops" in tool_names
