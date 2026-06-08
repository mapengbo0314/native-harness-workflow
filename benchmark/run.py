"""Benchmark runner — thin wrapper around the harness-bench (clawbench_v2) CLI.

New usage (harness-bench based):
    # List available tasks
    python benchmark/run.py tasks

    # Run a single task with one model
    python benchmark/run.py run-task --task A-bug-fix-001 --model claude-no-harness --mode live

    # Run all tasks with one model
    python benchmark/run.py run-suite --model claude-no-harness --mode live

    # Keep the original benchmark runner (legacy):
    python benchmark/run.py --legacy [--config full_harness] [--scenario A_bug_fix/001]

The wrapper sets the CLAWBENCHV2_APP_CONFIG and CLAWBENCHV2_MODELS_CONFIG env vars
to point at benchmark/config/ before delegating to clawbench_v2.cli.main().

Legacy flags (--config, --scenario, --provider, --timeout, --judge-provider) still
delegate to the old runner.session / runner.scorer pipeline so existing workflows
keep working during the transition.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── locate repo root and benchmark dir ──────────────────────────────────────
_BENCH_DIR = Path(__file__).resolve().parent          # benchmark/
_REPO_ROOT  = _BENCH_DIR.parent                       # repo root

# ── expose clawbench_v2 as an importable package ────────────────────────────
sys.path.insert(0, str(_BENCH_DIR))                   # so `import clawbench_v2` works

# ── set config env vars before importing clawbench_v2.cli ───────────────────
os.environ.setdefault(
    "CLAWBENCHV2_APP_CONFIG",
    str(_BENCH_DIR / "config" / "app.yaml"),
)
os.environ.setdefault(
    "CLAWBENCHV2_MODELS_CONFIG",
    str(_BENCH_DIR / "config" / "models.yaml"),
)
# Tell clawbench_v2.config.resolve_project_root() where the repo root is
os.environ.setdefault("CLAWBENCHV2_PROJECT_ROOT", str(_REPO_ROOT))

# ── also add repo/src to PYTHONPATH so harness modules are importable ────────
_repo_src = str(_REPO_ROOT / "src")
if _repo_src not in sys.path:
    sys.path.insert(0, _repo_src)


def _is_legacy() -> bool:
    """Return True if any legacy flag is present on the command line."""
    legacy_flags = {"--config", "--scenario", "--provider", "--judge-provider", "--timeout", "--legacy"}
    return bool(legacy_flags.intersection(sys.argv[1:]))


def _run_legacy() -> None:
    """Delegate to the original benchmark runner."""
    # Remove --legacy flag if present (not understood by original main)
    if "--legacy" in sys.argv:
        sys.argv.remove("--legacy")

    # Add benchmark/ to the path so `from runner.session import ...` works
    _bench_runner = str(_BENCH_DIR)
    if _bench_runner not in sys.path:
        sys.path.insert(0, _bench_runner)

    from runner.session import run_scenario          # noqa: F401 (side-effect import)
    from runner.scorer import score_session          # noqa: F401
    from runner.report import build_report, save_report, print_summary  # noqa: F401
    from runner.providers import SUPPORTED_PROVIDERS  # noqa: F401

    import argparse

    SCENARIOS_DIR = _BENCH_DIR / "scenarios"
    RESULTS_DIR = _BENCH_DIR / "results"
    CONFIGS = ["no_harness", "minimal", "full_harness", "rtk", "full_harness_rtk"]

    def _collect_scenarios(scenarios_dir: Path, filter_str: str | None) -> list[Path]:
        yaml_files = {f.stem: f for f in sorted(scenarios_dir.rglob("*.yaml"))
                      if "criteria" not in f.name}
        md_files = {f.stem: f for f in sorted(scenarios_dir.rglob("*.md"))}
        all_scenarios = list({**md_files, **yaml_files}.values())
        if filter_str:
            all_scenarios = [f for f in all_scenarios if filter_str in str(f)]
        return sorted(all_scenarios)

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None)
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default="claude")
    parser.add_argument("--judge-provider", choices=SUPPORTED_PROVIDERS, default=None)
    parser.add_argument("--legacy", action="store_true", help="Force legacy runner")
    args = parser.parse_args()
    judge_provider = args.judge_provider or args.provider

    configs = [c.strip() for c in args.config.split(",")] if args.config else CONFIGS
    scenario_files = _collect_scenarios(SCENARIOS_DIR, args.scenario)

    all_scores = []
    for config in configs:
        for scenario_path in scenario_files:
            print(
                f"Running {scenario_path.parent.name}/{scenario_path.stem} "
                f"[{config}, agent={args.provider}, judge={judge_provider}]...",
                flush=True,
            )
            try:
                result = run_scenario(
                    scenario_path, config, provider=args.provider, timeout=args.timeout
                )
                if scenario_path.suffix == ".yaml":
                    score = score_session(result, scenario_path, judge_provider=judge_provider)
                else:
                    criteria_path = scenario_path.parent / (scenario_path.stem.split("_")[0] + "_criteria.yaml")
                    score = score_session(result, criteria_path, judge_provider=judge_provider)
                all_scores.append(score)
                print(
                    f"  score={score.score:.1%} turns={score.turns} "
                    f"agent_tokens={score.agent_usage.as_dict()['total_tokens']:,} "
                    f"judge_tokens={score.judge_usage.as_dict()['total_tokens']:,}",
                    flush=True,
                )
            except Exception as e:
                print(f"  ERROR: {e}", flush=True)

    report = build_report(all_scores)
    report_path = save_report(report, RESULTS_DIR)
    print_summary(report)
    print(f"\nReport saved to {report_path}")


def main() -> None:
    if _is_legacy():
        _run_legacy()
        return

    # Delegate to clawbench_v2 CLI
    from clawbench_v2.cli import main as _clawbench_main
    raise SystemExit(_clawbench_main())


if __name__ == "__main__":
    main()
