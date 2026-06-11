"""Phase 5 (F2 ECC port): adversary pipeline — risk-report staleness checker.

`scripts/check_risk_report.py` is the deterministic helper the skill-text gate
invokes (C3: there is no dispatcher insertion point — the gate lives in
`harness-brainstorming-plans` / `harness-requesting-code-review` skill text,
advisory semantics accepted in writing).

Contract:
  - exit 0 when a matching risk report exists in the reports dir AND is newer
    than the design doc (mtime compare)
  - exit 1 when no matching report exists ("missing")
  - exit 1 when the report is older than the design doc ("stale")
  - toggle off (`pipeline.dispatcher.gates.adversary_exit=false`) ⇒ exit 0
  - reports match on <topic>: design `YYYY-MM-DD-<topic>-design.md` pairs with
    `*-<topic>-risk-report.md` (review date may differ from design date)
  - nonexistent design doc ⇒ exit nonzero with a clear error
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).parent.parent.parent
    / "src/harness/templates/boilerplate/scripts/check_risk_report.py"
)


@pytest.fixture
def plugin_root(tmp_path):
    root = tmp_path / "plugin"
    (root / "state").mkdir(parents=True)
    return root


@pytest.fixture
def project(tmp_path):
    """A fake target project with a design doc and a reports dir."""
    designs = tmp_path / "docs" / "designs"
    designs.mkdir(parents=True)
    reports = tmp_path / "docs" / "adversary"
    reports.mkdir(parents=True)
    design = designs / "2026-06-10-widget-sync-design.md"
    design.write_text("# design\n")
    return {"root": tmp_path, "design": design, "reports": reports}


def _write_report(reports_dir: Path, name: str, newer_than: Path = None) -> Path:
    report = reports_dir / name
    report.write_text("# risk report\n")
    if newer_than is not None:
        base = newer_than.stat().st_mtime
        os.utime(report, (base + 60, base + 60))
    return report


def _run(plugin_root: Path, *args):
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


class TestStalenessChecker:
    def test_fresh_report_passes(self, plugin_root, project):
        _write_report(
            project["reports"],
            "2026-06-11-widget-sync-risk-report.md",
            newer_than=project["design"],
        )
        p = _run(plugin_root, str(project["design"]), "--reports-dir", str(project["reports"]))
        assert p.returncode == 0, p.stderr
        assert "risk report" in (p.stdout + p.stderr).lower()

    def test_missing_report_fails(self, plugin_root, project):
        p = _run(plugin_root, str(project["design"]), "--reports-dir", str(project["reports"]))
        assert p.returncode == 1
        assert "no risk report" in p.stderr.lower()
        assert "widget-sync" in p.stderr

    def test_stale_report_fails(self, plugin_root, project):
        report = _write_report(project["reports"], "2026-06-09-widget-sync-risk-report.md")
        base = project["design"].stat().st_mtime
        os.utime(report, (base - 60, base - 60))
        p = _run(plugin_root, str(project["design"]), "--reports-dir", str(project["reports"]))
        assert p.returncode == 1
        assert "stale" in p.stderr.lower() or "older" in p.stderr.lower()

    def test_other_topic_report_does_not_count(self, plugin_root, project):
        _write_report(
            project["reports"],
            "2026-06-11-other-topic-risk-report.md",
            newer_than=project["design"],
        )
        p = _run(plugin_root, str(project["design"]), "--reports-dir", str(project["reports"]))
        assert p.returncode == 1
        assert "no risk report" in p.stderr.lower()

    def test_newest_matching_report_wins(self, plugin_root, project):
        """Stale + fresh report for the same topic ⇒ fresh one satisfies the gate."""
        stale = _write_report(project["reports"], "2026-06-08-widget-sync-risk-report.md")
        base = project["design"].stat().st_mtime
        os.utime(stale, (base - 120, base - 120))
        _write_report(
            project["reports"],
            "2026-06-11-widget-sync-risk-report.md",
            newer_than=project["design"],
        )
        p = _run(plugin_root, str(project["design"]), "--reports-dir", str(project["reports"]))
        assert p.returncode == 0, p.stderr

    def test_missing_design_doc_errors(self, plugin_root, project):
        p = _run(plugin_root, str(project["root"] / "docs/designs/nope-design.md"),
                 "--reports-dir", str(project["reports"]))
        assert p.returncode not in (0,)
        assert "design doc" in p.stderr.lower()


class TestToggle:
    def test_toggle_off_passes_without_report(self, plugin_root, project):
        (plugin_root / "features.json").write_text(
            json.dumps({"pipeline": {"dispatcher": {"gates": {"adversary_exit": False}}}})
        )
        p = _run(plugin_root, str(project["design"]), "--reports-dir", str(project["reports"]))
        assert p.returncode == 0, p.stderr
        assert "off" in (p.stdout + p.stderr).lower()

    def test_toggle_on_still_enforces(self, plugin_root, project):
        (plugin_root / "features.json").write_text(
            json.dumps({"pipeline": {"dispatcher": {"gates": {"adversary_exit": True}}}})
        )
        p = _run(plugin_root, str(project["design"]), "--reports-dir", str(project["reports"]))
        assert p.returncode == 1


class TestTopicExtraction:
    def test_design_doc_without_date_prefix_still_matches(self, plugin_root, tmp_path):
        designs = tmp_path / "docs" / "designs"
        designs.mkdir(parents=True)
        reports = tmp_path / "docs" / "adversary"
        reports.mkdir(parents=True)
        design = designs / "widget-sync-design.md"
        design.write_text("# design\n")
        _write_report(reports, "2026-06-11-widget-sync-risk-report.md", newer_than=design)
        p = _run(plugin_root, str(design), "--reports-dir", str(reports))
        assert p.returncode == 0, p.stderr
