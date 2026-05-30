"""
RED test for S1-T1: mint_platform fixture.

Verified plugin-root conventions (from actual mint runs):
  - claude:  <project>/.claude/plugin-generated/  (hooks.json, agents.json, agents/, skills/ all live here)
  - gemini:  <project>/.gemini/                   (hooks.json, agents/, skills/ live directly here)
"""
import pytest
from pathlib import Path

from tests.e2e._mint_helpers import mint_platform


@pytest.mark.parametrize("platform,hooks_rel,agents_rel", [
    ("claude", "hooks/hooks.json", "agents"),
    ("gemini", "hooks/hooks.json", "agents"),
])
def test_mint_platform_returns_existing_dir(tmp_path, platform, hooks_rel, agents_rel):
    """mint_platform must return a Path that exists and is a directory."""
    plugin_root = mint_platform(tmp_path, platform)
    assert isinstance(plugin_root, Path)
    assert plugin_root.exists(), f"{platform}: returned root does not exist: {plugin_root}"
    assert plugin_root.is_dir(), f"{platform}: returned root is not a directory: {plugin_root}"


@pytest.mark.parametrize("platform,hooks_rel,agents_rel", [
    ("claude", "hooks/hooks.json", "agents"),
    ("gemini", "hooks/hooks.json", "agents"),
])
def test_mint_platform_wiring_artifacts_present(tmp_path, platform, hooks_rel, agents_rel):
    """plugin root must contain the canonical wiring artifacts."""
    plugin_root = mint_platform(tmp_path, platform)

    hooks_path = plugin_root / hooks_rel
    agents_dir = plugin_root / agents_rel

    assert hooks_path.exists(), (
        f"{platform}: hooks config missing at {hooks_path}\n"
        f"  plugin_root contents: {sorted(str(p.relative_to(plugin_root)) for p in plugin_root.rglob('*') if p.is_file())[:20]}"
    )
    assert agents_dir.is_dir(), (
        f"{platform}: agents directory missing at {agents_dir}\n"
        f"  plugin_root contents: {sorted(str(p.relative_to(plugin_root)) for p in plugin_root.rglob('*') if p.is_file())[:20]}"
    )


def test_mint_platform_claude_has_agents_json(tmp_path):
    """Claude plugin root specifically must contain agents.json (plugin manifest)."""
    plugin_root = mint_platform(tmp_path, "claude")
    agents_json = plugin_root / "agents.json"
    assert agents_json.exists(), (
        f"claude: agents.json missing at {agents_json}\n"
        f"  plugin_root: {plugin_root}"
    )
