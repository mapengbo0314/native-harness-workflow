"""B3 — regenerate_derived() and DERIVED_FROM classification mapping.

Tests cover:
- Basic regeneration: agents.json and rules.json are written from .md sources;
  orchestrator.json is NOT created when orchestrator.md is absent (graceful skip).
- Embedded source content: the "source" field in agents.json matches the .md content.
- Consistency-with-merge: editing a .md and re-running reflects the new content.
- Idempotency: two consecutive regenerations produce identical JSON output.
- DERIVED_FROM mapping correctness (D8).
- DERIVED_FILES still classifies the three derived filenames as class="derived".
"""
import json
import pytest
from pathlib import Path

from harness.init.plugin_generator import regenerate_derived
from harness.update.classification import DERIVED_FROM, DERIVED_FILES, classify


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def plugin_dir(tmp_path: Path) -> Path:
    """Minimal plugin dir with agents/ and rules/ but NO orchestrator.md."""
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "a.md").write_text("# Agent A\nDoes alpha tasks.")
    (agents / "b.md").write_text("# Agent B\nDoes beta tasks.")

    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "r.md").write_text("# Rule R\nBe excellent.")

    return tmp_path


# ---------------------------------------------------------------------------
# Basic regeneration
# ---------------------------------------------------------------------------

def test_regenerate_creates_agents_and_rules_json(plugin_dir: Path):
    result = regenerate_derived(plugin_dir)
    assert "agents.json" in result
    assert "rules.json" in result
    assert (plugin_dir / "agents.json").exists()
    assert (plugin_dir / "rules.json").exists()


def test_regenerate_skips_orchestrator_when_absent(plugin_dir: Path):
    """No orchestrator.md → orchestrator.json must NOT be created."""
    result = regenerate_derived(plugin_dir)
    assert "orchestrator.json" not in result
    assert not (plugin_dir / "orchestrator.json").exists()


def test_regenerate_skips_orchestrator_gracefully_with_harness_dir(plugin_dir: Path, tmp_path: Path):
    """harness_dir given but orchestrator.md missing there → still no error, no file."""
    harness_dir = tmp_path / "harness_root"
    harness_dir.mkdir()
    result = regenerate_derived(plugin_dir, harness_dir=harness_dir)
    assert "orchestrator.json" not in result
    assert not (plugin_dir / "orchestrator.json").exists()


def test_regenerate_creates_orchestrator_when_present(plugin_dir: Path, tmp_path: Path):
    """When orchestrator.md exists in harness_dir, orchestrator.json is created."""
    harness_dir = tmp_path / "harness_root"
    harness_dir.mkdir()
    (harness_dir / "orchestrator.md").write_text("# Orchestrator\nRoutes tasks.")
    result = regenerate_derived(plugin_dir, harness_dir=harness_dir)
    assert "orchestrator.json" in result
    assert (plugin_dir / "orchestrator.json").exists()


def test_regenerate_skips_missing_agents_dir(tmp_path: Path):
    """If agents/ is absent, agents.json is NOT produced (no error)."""
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "r.md").write_text("Rule text.")
    result = regenerate_derived(tmp_path)
    assert "agents.json" not in result
    assert not (tmp_path / "agents.json").exists()
    assert "rules.json" in result


def test_regenerate_skips_missing_rules_dir(tmp_path: Path):
    """If rules/ is absent, rules.json is NOT produced (no error)."""
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "x.md").write_text("Agent X.")
    result = regenerate_derived(tmp_path)
    assert "rules.json" not in result
    assert not (tmp_path / "rules.json").exists()
    assert "agents.json" in result


# ---------------------------------------------------------------------------
# Source content embedding
# ---------------------------------------------------------------------------

def test_agents_json_embeds_source_text(plugin_dir: Path):
    """The 'source' field for each agent must equal the raw .md content."""
    regenerate_derived(plugin_dir)
    data = json.loads((plugin_dir / "agents.json").read_text())
    agents = data["agents"]
    assert agents["a"]["source"] == "# Agent A\nDoes alpha tasks."
    assert agents["b"]["source"] == "# Agent B\nDoes beta tasks."


def test_agents_json_count_matches_md_files(plugin_dir: Path):
    regenerate_derived(plugin_dir)
    data = json.loads((plugin_dir / "agents.json").read_text())
    assert data["count"] == 2


def test_rules_json_embeds_source_text(plugin_dir: Path):
    """The rules dict must map rule name to raw .md content."""
    regenerate_derived(plugin_dir)
    data = json.loads((plugin_dir / "rules.json").read_text())
    assert data["rules"]["r"] == "# Rule R\nBe excellent."
    assert data["count"] == 1


# ---------------------------------------------------------------------------
# Consistency-with-merge
# ---------------------------------------------------------------------------

def test_edited_md_reflected_in_regenerated_json(plugin_dir: Path):
    """After editing a .md, re-running regenerate_derived must update the JSON."""
    regenerate_derived(plugin_dir)

    # Simulate a merge edit to agents/a.md
    (plugin_dir / "agents" / "a.md").write_text("# Agent A v2\nDoes improved alpha tasks.")

    regenerate_derived(plugin_dir)

    data = json.loads((plugin_dir / "agents.json").read_text())
    assert data["agents"]["a"]["source"] == "# Agent A v2\nDoes improved alpha tasks."


def test_new_md_included_after_regeneration(plugin_dir: Path):
    """A new .md added after first mint is picked up by the next regeneration."""
    regenerate_derived(plugin_dir)
    data_before = json.loads((plugin_dir / "agents.json").read_text())
    assert "c" not in data_before["agents"]

    (plugin_dir / "agents" / "c.md").write_text("# Agent C\nNew agent.")
    regenerate_derived(plugin_dir)

    data_after = json.loads((plugin_dir / "agents.json").read_text())
    assert "c" in data_after["agents"]
    assert data_after["count"] == 3


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_idempotent_agents_json(plugin_dir: Path):
    """Two consecutive regenerations produce byte-identical agents.json."""
    regenerate_derived(plugin_dir)
    first = (plugin_dir / "agents.json").read_text()
    regenerate_derived(plugin_dir)
    second = (plugin_dir / "agents.json").read_text()
    assert first == second


def test_idempotent_rules_json(plugin_dir: Path):
    """Two consecutive regenerations produce byte-identical rules.json."""
    regenerate_derived(plugin_dir)
    first = (plugin_dir / "rules.json").read_text()
    regenerate_derived(plugin_dir)
    second = (plugin_dir / "rules.json").read_text()
    assert first == second


# ---------------------------------------------------------------------------
# DERIVED_FROM mapping (D8)
# ---------------------------------------------------------------------------

def test_derived_from_maps_all_three_derived_files():
    assert set(DERIVED_FROM.keys()) == {"agents.json", "rules.json", "orchestrator.json"}


def test_derived_from_agents_json_points_to_agents_dir():
    assert DERIVED_FROM["agents.json"] == "agents"


def test_derived_from_rules_json_points_to_rules_dir():
    assert DERIVED_FROM["rules.json"] == "rules"


def test_derived_from_orchestrator_json_points_to_orchestrator_md():
    assert DERIVED_FROM["orchestrator.json"] == "orchestrator.md"


# ---------------------------------------------------------------------------
# Classification still correct for derived files
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", ["agents.json", "rules.json", "orchestrator.json"])
def test_derived_files_classified_as_derived(filename: str):
    """All three derived JSON files must classify as class='derived', producer='export'."""
    o = classify(filename)
    assert o is not None
    assert o.cls == "derived"
    assert o.producer == "export"
    assert o.source_rel is None


def test_derived_files_set_matches_derived_from_keys():
    """DERIVED_FILES frozenset must match the keys of DERIVED_FROM (same three files)."""
    assert DERIVED_FILES == frozenset(DERIVED_FROM.keys())
