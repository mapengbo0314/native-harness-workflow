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
        summary[config] = {
            "scenarios_run": len(config_scores),
            "avg_score": round(avg_score, 3),
            "avg_turns": round(avg_turns, 1),
            "scenarios": [
                {
                    "id": s.scenario_id,
                    "score": round(s.score, 3),
                    "turns": s.turns,
                    "session_id": s.session_id,
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
        "configs": summary,
    }


def save_report(report: dict, results_dir: Path) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = results_dir / f"report_{ts}.json"
    path.write_text(json.dumps(report, indent=2))
    return path


def print_summary(report: dict) -> None:
    print(f"\n{'Config':<15} {'Scenarios':>10} {'Avg Score':>10} {'Avg Turns':>10}")
    print("-" * 50)
    for config, data in report["configs"].items():
        print(f"{config:<15} {data['scenarios_run']:>10} {data['avg_score']:>10.1%} {data['avg_turns']:>10.1f}")
