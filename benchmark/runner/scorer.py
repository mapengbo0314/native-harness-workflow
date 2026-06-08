"""Score a session transcript against scenario acceptance criteria using a judge model."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from .providers import TokenUsage, run_judge
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
    provider: str
    judge_provider: str
    total_weight: int
    earned_weight: int
    score: float  # 0.0–1.0
    criteria: list[CriterionScore]
    turns: int
    agent_usage: TokenUsage
    judge_usage: TokenUsage
    transcript: str
    error: str | None


def score_session(
    result: SessionResult,
    criteria_path: Path,
    judge_provider: str = "claude",
) -> ScenarioScore:
    """Score a session result against its criteria file using a judge model."""
    criteria_def = yaml.safe_load(criteria_path.read_text())
    # Support both inline criteria (new .yaml) and standalone criteria file
    criteria_list = criteria_def.get("criteria") if isinstance(criteria_def, dict) else None
    if criteria_list is None:
        criteria_list = criteria_def
    transcript_text = result.full_transcript

    judged, judge_usage = _judge_criteria(
        transcript_text, criteria_list, judge_provider
    )
    scores = []
    for criterion in criteria_list:
        verdict = judged.get(
            criterion["id"],
            {"passed": False, "reasoning": "judge omitted criterion"},
        )
        scores.append(CriterionScore(
            id=criterion["id"],
            description=criterion["description"],
            weight=criterion["weight"],
            passed=bool(verdict["passed"]),
            reasoning=str(verdict["reasoning"]),
        ))

    total = sum(c.weight for c in scores)
    earned = sum(c.weight for c in scores if c.passed)

    return ScenarioScore(
        scenario_id=result.scenario_id,
        config=result.config,
        session_id=result.session_id,
        provider=result.provider,
        judge_provider=judge_provider,
        total_weight=total,
        earned_weight=earned,
        score=earned / total if total > 0 else 0.0,
        criteria=scores,
        turns=result.turn_count,
        agent_usage=result.agent_usage,
        judge_usage=judge_usage,
        transcript=result.full_transcript,
        error=result.error,
    )


def _judge_criteria(
    transcript: str,
    criteria: list[dict],
    judge_provider: str,
) -> tuple[dict[str, dict], TokenUsage]:
    """Evaluate all criteria in one judge call to avoid repeating transcripts."""
    requested = [
        {"id": item["id"], "description": item["description"]}
        for item in criteria
    ]
    prompt = (
        "You are a strict evaluator. Evaluate every criterion against the "
        "transcript. Return one verdict per criterion ID.\n\n"
        f"Criteria:\n{json.dumps(requested)}\n\n"
        f"Transcript:\n{_compact_transcript(transcript)}\n\n"
        "Reply with JSON only, no other text: "
        '{"criteria":[{"id":"criterion_id","passed":true,'
        '"reasoning":"one sentence"}]}'
    )
    try:
        result = run_judge(judge_provider, prompt, timeout=120)
        output = result.text
        # extract JSON even if there's surrounding text
        start = output.find("{")
        end = output.rfind("}") + 1
        parsed = json.loads(output[start:end])
        verdicts = {
            item["id"]: {
                "passed": bool(item["passed"]),
                "reasoning": item["reasoning"],
            }
            for item in parsed["criteria"]
        }
        return verdicts, result.usage
    except Exception as e:
        return {
            item["id"]: {
                "passed": False,
                "reasoning": f"judge error: {e}",
            }
            for item in criteria
        }, TokenUsage()


def _compact_transcript(transcript: str, max_chars: int = 12000) -> str:
    """Keep the prompt, command list, and final answer when a trace is large."""
    if len(transcript) <= max_chars:
        return transcript

    commands = "\n".join(
        line for line in transcript.splitlines() if line.startswith("COMMAND:")
    )
    if len(commands) > 2000:
        commands = (
            commands[:1000]
            + "\n... [command summary compacted] ...\n"
            + commands[-1000:]
        )
    prefix_chars = min(1500, max_chars // 4)
    prefix = transcript[:prefix_chars]
    separators = (
        "\n\n... [middle of transcript compacted] ...\n\n"
        "COMMAND SUMMARY:\n"
        "\n\nFINAL TRANSCRIPT:\n"
    )
    suffix_chars = max_chars - len(prefix) - len(commands) - len(separators)
    if suffix_chars < 1000:
        suffix_chars = 1000
        commands = commands[: max(0, max_chars - len(prefix) - suffix_chars - len(separators))]
    suffix = transcript[-suffix_chars:]
    return (
        f"{prefix}\n\n"
        f"... [middle of transcript compacted] ...\n\n"
        f"COMMAND SUMMARY:\n{commands}\n\n"
        f"FINAL TRANSCRIPT:\n{suffix}"
    )
