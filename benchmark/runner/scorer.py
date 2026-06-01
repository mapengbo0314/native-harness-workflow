"""Score a session transcript against scenario acceptance criteria using a judge model."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from .session import SessionResult


@dataclass
class CriterionScore:
    id: str
    description: str
    weight: int
    passed: bool
    reasoning: str


@dataclass
class ScenarioScore:
    scenario_id: str
    config: str
    session_id: str
    total_weight: int
    earned_weight: int
    score: float  # 0.0–1.0
    criteria: list[CriterionScore]
    turns: int


def score_session(result: SessionResult, criteria_path: Path) -> ScenarioScore:
    """Score a session result against its criteria file using a judge model."""
    criteria_def = yaml.safe_load(criteria_path.read_text())
    transcript_text = "\n".join(result.transcript)

    scores = []
    for criterion in criteria_def["criteria"]:
        passed, reasoning = _judge_criterion(
            transcript_text, criterion["description"]
        )
        scores.append(CriterionScore(
            id=criterion["id"],
            description=criterion["description"],
            weight=criterion["weight"],
            passed=passed,
            reasoning=reasoning,
        ))

    total = sum(c.weight for c in scores)
    earned = sum(c.weight for c in scores if c.passed)

    return ScenarioScore(
        scenario_id=result.scenario_id,
        config=result.config,
        session_id=result.session_id,
        total_weight=total,
        earned_weight=earned,
        score=earned / total if total > 0 else 0.0,
        criteria=scores,
        turns=result.turns,
    )


def _judge_criterion(transcript: str, criterion: str) -> tuple[bool, str]:
    """Use the Claude CLI as a judge to evaluate whether a criterion was met."""
    import subprocess
    prompt = (
        f"You are a strict evaluator. Given this transcript, did the agent meet "
        f"the following criterion?\n\nCriterion: {criterion}\n\n"
        f"Transcript:\n{transcript[:4000]}\n\n"
        f"Reply with JSON only, no other text: "
        f'{{\"passed\": true/false, \"reasoning\": \"one sentence\"}}'
    )
    try:
        result = subprocess.run(
            ["claude", "--print", "--dangerously-skip-permissions"],
            input=prompt, capture_output=True, text=True, timeout=60,
        )
        output = result.stdout.strip()
        # extract JSON even if there's surrounding text
        start = output.find("{")
        end = output.rfind("}") + 1
        parsed = json.loads(output[start:end])
        return bool(parsed["passed"]), parsed["reasoning"]
    except Exception as e:
        return False, f"judge error: {e}"
