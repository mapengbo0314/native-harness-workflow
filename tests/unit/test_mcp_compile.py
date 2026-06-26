"""Increment 4 (plugin-selector): MCP server toggles.

`filter_mcp_servers` is a pure filter; `compile_mcp_config` reads a non-destructive
catalog (`mcp_servers.json`) + `features.json` and writes the active `.mcp.json`.
Disabled servers (mcp.<name> == false) are dropped; absent flags fail-open (kept).
"""
from __future__ import annotations

import json
from pathlib import Path


def test_filter_mcp_servers_drops_disabled_and_keeps_absent():
    from harness.init.features import filter_mcp_servers

    catalog = {"mcpServers": {"domain": {"command": "d"}, "codegraph": {"command": "c"}}}
    features = {"mcp": {"codegraph": False}}  # domain absent -> kept (fail-open)
    out = filter_mcp_servers(catalog, features)
    assert set(out["mcpServers"].keys()) == {"domain"}


def test_filter_mcp_servers_is_pure():
    from harness.init.features import filter_mcp_servers

    catalog = {"mcpServers": {"domain": {"command": "d"}}}
    filter_mcp_servers(catalog, {"mcp": {"domain": False}})
    # Original catalog untouched.
    assert "domain" in catalog["mcpServers"]


def test_compile_mcp_config_writes_filtered_active_file(tmp_path):
    from harness.init.features import compile_mcp_config

    (tmp_path / "mcp_servers.json").write_text(
        json.dumps({"mcpServers": {"domain": {"command": "d"}, "codegraph": {"command": "c"}}}),
        encoding="utf-8",
    )
    (tmp_path / "features.json").write_text(
        json.dumps({"mcp": {"codegraph": False}}), encoding="utf-8"
    )
    out = compile_mcp_config(tmp_path)
    assert out == tmp_path / ".mcp.json"
    active = json.loads(out.read_text(encoding="utf-8"))
    assert set(active["mcpServers"].keys()) == {"domain"}
    # Catalog (source of truth) is never mutated.
    catalog = json.loads((tmp_path / "mcp_servers.json").read_text(encoding="utf-8"))
    assert "codegraph" in catalog["mcpServers"]


def test_compile_mcp_config_no_catalog_is_noop(tmp_path):
    from harness.init.features import compile_mcp_config

    assert compile_mcp_config(tmp_path) is None
    assert not (tmp_path / ".mcp.json").exists()
