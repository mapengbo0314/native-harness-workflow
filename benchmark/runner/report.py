"""Aggregate scores across configs and emit a comparison report."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .scorer import ScenarioScore


CONFIGS = ["no_harness", "minimal", "full_harness"]
CATEGORY_PREFIXES = ("A_", "B_", "C_", "E_", "F_rtk")


def _category_for(scenario_id: str) -> str | None:
    """Return the category prefix this scenario belongs to (A_, B_, C_, E_, F_rtk).

    Scenario IDs in this benchmark look like ``A-001``, ``F-RTK-002`` etc.
    We normalise on the dash-separated leading token.
    """
    if not scenario_id:
        return None
    sid_upper = scenario_id.upper()
    # F_rtk is a compound prefix — check it first.
    if sid_upper.startswith("F-RTK") or sid_upper.startswith("F_RTK"):
        return "F_rtk"
    if sid_upper[:1] in {"A", "B", "C", "E"} and sid_upper[1:2] in {"-", "_"}:
        return f"{sid_upper[0]}_"
    return None


def _avg_excluding_judge_failures(config_scores: list[ScenarioScore]) -> float:
    """Mean score over scenarios whose judge succeeded.

    A judge crash (``error == "judge_failed"``) is not evidence that the agent
    failed the criteria — exclude those scenarios from ``avg_score`` so the
    headline number reflects actual agent performance.
    """
    valid = [s for s in config_scores if s.error != "judge_failed"]
    if not valid:
        return 0.0
    return sum(s.score for s in valid) / len(valid)


def build_report(scores: list[ScenarioScore]) -> dict:
    """Aggregate scores by config and return a comparison report dict."""
    by_config: dict[str, list[ScenarioScore]] = {c: [] for c in CONFIGS}
    for s in scores:
        by_config.setdefault(s.config, []).append(s)

    summary = {}
    for config, config_scores in by_config.items():
        if not config_scores:
            continue
        avg_score = _avg_excluding_judge_failures(config_scores)
        judge_failures = sum(1 for s in config_scores if s.error == "judge_failed")
        avg_turns = sum(s.turns for s in config_scores) / len(config_scores)
        agent_usage = _sum_usage(s.agent_usage for s in config_scores)
        judge_usage = _sum_usage(s.judge_usage for s in config_scores)

        # Per-category breakdown so F-RTK results don't contaminate the
        # cross-config headline number.
        by_category: dict[str, list[ScenarioScore]] = {
            cat: [] for cat in CATEGORY_PREFIXES
        }
        for s in config_scores:
            cat = _category_for(s.scenario_id)
            if cat is not None:
                by_category[cat].append(s)

        categories = {}
        for cat, cat_scores in by_category.items():
            if not cat_scores:
                continue
            categories[cat] = {
                "scenarios_run": len(cat_scores),
                "avg_score": round(_avg_excluding_judge_failures(cat_scores), 3),
                "judge_failures": sum(
                    1 for s in cat_scores if s.error == "judge_failed"
                ),
            }

        summary[config] = {
            "scenarios_run": len(config_scores),
            "avg_score": round(avg_score, 3),
            "judge_failures": judge_failures,
            "avg_turns": round(avg_turns, 1),
            "agent_usage": agent_usage,
            "judge_usage": judge_usage,
            "categories": categories,
            "scenarios": [
                {
                    "id": s.scenario_id,
                    "score": round(s.score, 3),
                    "turns": s.turns,
                    "session_id": s.session_id,
                    "agent_usage": s.agent_usage.as_dict(),
                    "judge_usage": s.judge_usage.as_dict(),
                    "error": s.error,
                    "transcript": s.transcript,
                    "criteria": [
                        {"id": c.id, "passed": c.passed, "reasoning": c.reasoning}
                        for c in s.criteria
                    ],
                }
                for s in config_scores
            ],
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": scores[0].provider if scores else None,
        "judge_provider": scores[0].judge_provider if scores else None,
        "agent_usage": _sum_usage(s.agent_usage for s in scores),
        "judge_usage": _sum_usage(s.judge_usage for s in scores),
        "configs": summary,
    }


def save_report(report: dict, results_dir: Path) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = results_dir / f"report_{ts}.json"
    path.write_text(json.dumps(report, indent=2))
    return path


def print_summary(report: dict) -> None:
    print(
        f"\nAgent: {report.get('provider') or 'n/a'} | "
        f"Judge: {report.get('judge_provider') or 'n/a'}"
    )
    print(
        f"\n{'Config':<18} {'Scenarios':>9} {'Score':>8} {'JudgeFail':>10} "
        f"{'Turns':>7} {'Agent tok':>11} {'Judge tok':>11}"
    )
    print("-" * 84)
    for config, data in report["configs"].items():
        print(
            f"{config:<18} {data['scenarios_run']:>9} "
            f"{data['avg_score']:>8.1%} "
            f"{data.get('judge_failures', 0):>10} "
            f"{data['avg_turns']:>7.1f} "
            f"{data['agent_usage']['total_tokens']:>11,} "
            f"{data['judge_usage']['total_tokens']:>11,}"
        )
        categories = data.get("categories") or {}
        for cat, cat_data in categories.items():
            print(
                f"  └─ {cat:<13} {cat_data['scenarios_run']:>9} "
                f"{cat_data['avg_score']:>8.1%} "
                f"{cat_data.get('judge_failures', 0):>10}"
            )
    print(
        f"\nTotal tokens: agent={report['agent_usage']['total_tokens']:,}, "
        f"judge={report['judge_usage']['total_tokens']:,}"
    )


def _sum_usage(usages) -> dict[str, int]:
    totals = {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "uncached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
    }
    for usage in usages:
        for key, value in usage.as_dict().items():
            totals[key] += value
    return totals
