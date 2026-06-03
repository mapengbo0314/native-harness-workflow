"""CLI entry point: run all scenarios across all configs and emit a report.

Usage:
    python benchmark/run.py
    python benchmark/run.py --config full_harness
    python benchmark/run.py --scenario A_bug_fix/001
"""
from __future__ import annotations

import argparse
from pathlib import Path

from runner.session import run_scenario
from runner.scorer import score_session
from runner.report import build_report, save_report, print_summary

SCENARIOS_DIR = Path(__file__).parent / "scenarios"
RESULTS_DIR = Path(__file__).parent / "results"
CONFIGS = ["no_harness", "minimal", "full_harness"]


def _collect_scenarios(scenarios_dir: Path, filter_str: str | None) -> list[Path]:
    """Return .yaml scenarios, falling back to .md if no .yaml exists for a stem."""
    yaml_files = {f.stem: f for f in sorted(scenarios_dir.rglob("*.yaml"))
                  if "criteria" not in f.name}
    md_files = {f.stem: f for f in sorted(scenarios_dir.rglob("*.md"))}
    # yaml wins; md fills gaps
    all_scenarios = list({**md_files, **yaml_files}.values())
    if filter_str:
        all_scenarios = [f for f in all_scenarios if filter_str in str(f)]
    return sorted(all_scenarios)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None, help="Run a single config only")
    parser.add_argument("--scenario", default=None, help="Run a single scenario (e.g. A_bug_fix/001)")
    args = parser.parse_args()

    configs = [args.config] if args.config else CONFIGS

    # Prefer .yaml (multi-turn) over .md (legacy single-turn) per scenario dir
    scenario_files = _collect_scenarios(SCENARIOS_DIR, args.scenario)

    all_scores = []
    for config in configs:
        for scenario_path in scenario_files:
            print(f"Running {scenario_path.parent.name}/{scenario_path.stem} [{config}]...")
            try:
                result = run_scenario(scenario_path, config)
                # criteria embedded in .yaml; fall back to sibling _criteria.yaml for .md
                if scenario_path.suffix == ".yaml":
                    score = score_session(result, scenario_path)
                else:
                    criteria_path = scenario_path.parent / (scenario_path.stem.split("_")[0] + "_criteria.yaml")
                    score = score_session(result, criteria_path)
                all_scores.append(score)
                print(f"  score={score.score:.1%} turns={score.turns}")
            except Exception as e:
                print(f"  ERROR: {e}")

    report = build_report(all_scores)
    report_path = save_report(report, RESULTS_DIR)
    print_summary(report)
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
