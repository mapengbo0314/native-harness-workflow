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


class TestGlobEscaping:
    def test_bracketed_design_doc_name_matches(self, plugin_root, tmp_path):
        """Phase 6a hardening (review finding #8): glob metacharacters in the
        topic must be escaped — 'auth[v2]' is a literal, not a char class."""
        designs = tmp_path / "docs" / "designs"
        designs.mkdir(parents=True)
        reports = tmp_path / "docs" / "adversary"
        reports.mkdir(parents=True)
        design = designs / "2026-06-11-auth[v2]-design.md"
        design.write_text("# design\n")
        _write_report(reports, "2026-06-11-auth[v2]-risk-report.md", newer_than=design)
        p = _run(plugin_root, str(design), "--reports-dir", str(reports))
        assert p.returncode == 0, p.stderr


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


# ---------------------------------------------------------------------------
# Contract: adversary-pipeline skill content + registration
# ---------------------------------------------------------------------------

BOILERPLATE = Path(__file__).parent.parent.parent / "src/harness/templates/boilerplate"
PIPELINE_SKILL = BOILERPLATE / "skills" / "adversary-pipeline" / "SKILL.md"
SKILLS_JSON = BOILERPLATE / "skills.json"
ADVERSARY_AGENT = BOILERPLATE / "agents" / "adversary.md"
BRAINSTORM_SKILL = BOILERPLATE / "skills" / "harness-brainstorming-plans" / "SKILL.md"
REVIEW_SKILL = BOILERPLATE / "skills" / "harness-requesting-code-review" / "SKILL.md"


class TestAdversaryPipelineSkillContract:
    def test_skill_exists_and_registered(self):
        assert PIPELINE_SKILL.exists(), "adversary-pipeline SKILL.md must be authored"
        skills = json.loads(SKILLS_JSON.read_text(encoding="utf-8"))["skills"]
        assert "adversary-pipeline" in skills
        assert skills["adversary-pipeline"]["path"] == "adversary-pipeline/SKILL.md"

    def test_tier1_is_default_inline_council(self):
        text = PIPELINE_SKILL.read_text(encoding="utf-8")
        assert "Tier 1" in text and "Tier 2" in text
        assert "council" in text.lower()
        for lens in ("Attacker", "Defender", "Auditor"):
            assert lens in text, f"role lens {lens} must be in the skill"
        assert "inline" in text.lower(), "Tier 1 must be inline (no subagents)"

    def test_tier2_dispatches_general_purpose_not_plugin_adversary(self):
        text = PIPELINE_SKILL.read_text(encoding="utf-8")
        assert "general-purpose" in text
        assert "orchestrator-plugin:adversary" not in text, (
            "Tier 2 must dispatch fresh general-purpose agents, never the "
            "inert plugin adversary agent"
        )
        assert "verify" in text.lower() and "real" in text.lower(), (
            "dispatches must carry verify-real-state instructions"
        )

    def test_tier2_arms_budget_sidecar_before_each_dispatch(self):
        """R5 + Phase 6a: the budget is enforced, not requested — the skill
        arms the sidecar via the deterministic session_phase.py CLI (no inline
        python heredocs) before each dispatch so pre_tool_use can hard-stop."""
        text = PIPELINE_SKILL.read_text(encoding="utf-8")
        assert "arm-budget" in text, "skill must arm via session_phase.py arm-budget"
        assert "disarm-budget" in text, "skill must disarm after each dispatch"
        assert "--session" in text, "skill must thread the session id explicitly"
        assert "python3 - <<" not in text, "no inline python heredocs (Phase 6a)"
        assert "before" in text.lower() and "dispatch" in text.lower()
        assert "30" in text and "12" in text, "default budgets (30 tool calls / 12 files)"
        assert "summarize" in text.lower(), "degrade-gracefully steering clause"

    def test_risk_report_output_path(self):
        text = PIPELINE_SKILL.read_text(encoding="utf-8")
        assert "docs/adversary/" in text
        assert "-risk-report.md" in text

    def test_prompt_defense_preamble_present(self):
        text = PIPELINE_SKILL.read_text(encoding="utf-8")
        assert "prompt" in text.lower() and "defense" in text.lower()


class TestAuditorPersonaRescope:
    def test_adversary_agent_rescoped_as_auditor(self):
        text = ADVERSARY_AGENT.read_text(encoding="utf-8")
        assert "Auditor" in text, (
            "agents/adversary.md must be re-scoped as the Auditor role the "
            "pipeline references"
        )
        assert "adversary-pipeline" in text


class TestAdversaryExitGateText:
    """C3: the exit gate lives in skill text (advisory semantics, accepted in
    writing) — both sign-off skills must invoke the staleness checker when
    pipeline.dispatcher.gates.adversary_exit is on."""

    def test_brainstorming_skill_gate_text(self):
        text = BRAINSTORM_SKILL.read_text(encoding="utf-8")
        assert "check_risk_report.py" in text
        assert "adversary_exit" in text

    def test_review_skill_gate_text(self):
        text = REVIEW_SKILL.read_text(encoding="utf-8")
        assert "check_risk_report.py" in text
        assert "adversary_exit" in text

    def test_brainstorming_part5_uses_pipeline_not_inert_agent(self):
        """Part 5 must route through the tiered adversary-pipeline skill, not
        a bare dispatch of the inert plugin adversary agent."""
        text = BRAINSTORM_SKILL.read_text(encoding="utf-8")
        assert "adversary-pipeline" in text
