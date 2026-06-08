"""Aggregate scores across configs and emit a comparison report."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .scorer import ScenarioScore


CONFIGS = ["no_harness", "minimal", "full_harness"]


def build_report(scores: list[ScenarioScore]) -> dict:
    """Aggregate scores by config and return a comparison report dict."""
    by_config: dict[str, list[ScenarioScore]] = {c: [] for c in CONFIGS}
    for s in scores:
        by_config.setdefault(s.config, []).append(s)

    summary = {}
    for config, config_scores in by_config.items():
        if not config_scores:
            continue
        avg_score = sum(s.score for s in config_scores) / len(config_scores)
        avg_turns = sum(s.turns for s in config_scores) / len(config_scores)
        agent_usage = _sum_usage(s.agent_usage for s in config_scores)
        judge_usage = _sum_usage(s.judge_usage for s in config_scores)
        summary[config] = {
            "scenarios_run": len(config_scores),
            "avg_score": round(avg_score, 3),
            "avg_turns": round(avg_turns, 1),
            "agent_usage": agent_usage,
            "judge_usage": judge_usage,
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
        f"\n{'Config':<18} {'Scenarios':>9} {'Score':>8} {'Turns':>7} "
        f"{'Agent tok':>11} {'Judge tok':>11}"
    )
    print("-" * 72)
    for config, data in report["configs"].items():
        print(
            f"{config:<18} {data['scenarios_run']:>9} "
            f"{data['avg_score']:>8.1%} {data['avg_turns']:>7.1f} "
            f"{data['agent_usage']['total_tokens']:>11,} "
            f"{data['judge_usage']['total_tokens']:>11,}"
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
