from __future__ import annotations

import json
import subprocess
from pathlib import Path

from benchmark.runner.providers import (
    _compact_command_output,
    _parse_codex_jsonl,
    run_agent_turn,
)
from benchmark.runner.scorer import _compact_transcript


def test_parse_codex_jsonl_captures_thread_commands_and_message():
    output = "\n".join([
        json.dumps({"type": "thread.started", "thread_id": "thread-123"}),
        json.dumps({
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "pytest -q",
                "aggregated_output": "1 passed",
            },
        }),
        json.dumps({
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "Done."},
        }),
        json.dumps({
            "type": "turn.completed",
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 60,
                "output_tokens": 20,
                "reasoning_output_tokens": 5,
            },
        }),
    ])

    thread_id, transcript, usage = _parse_codex_jsonl(output)

    assert thread_id == "thread-123"
    assert "COMMAND: pytest -q" in transcript
    assert "1 passed" in transcript
    assert "ASSISTANT: Done." in transcript
    assert usage.input_tokens == 100
    assert usage.cached_input_tokens == 60
    assert usage.output_tokens == 20
    assert usage.reasoning_output_tokens == 5
    assert usage.as_dict()["total_tokens"] == 120


def test_codex_first_turn_uses_project_and_json(monkeypatch, tmp_path):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        stdout = "\n".join([
            json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
            json.dumps({
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "ok"},
            }),
        ])
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_agent_turn(
        "codex", "do work", Path(tmp_path), 30, system_prompt="Use RTK."
    )

    assert captured["command"][:3] == ["codex", "exec", "--json"]
    assert ["-C", str(tmp_path)] == captured["command"][-3:-1]
    assert captured["input"] == "Use RTK.\n\ndo work"
    assert result.session_id == "thread-1"


def test_codex_followup_resumes_thread(monkeypatch, tmp_path):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "continued"},
            }),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_agent_turn(
        "codex", "next", Path(tmp_path), 30, session_id="thread-1"
    )

    assert captured["command"][:3] == ["codex", "exec", "resume"]
    assert "thread-1" in captured["command"]
    assert result.session_id == "thread-1"


def test_compact_command_output_keeps_head_and_tail():
    output = "A" * 1000 + "B" * 1000
    compacted = _compact_command_output(output, max_chars=200)

    assert compacted.startswith("A" * 100)
    assert compacted.endswith("B" * 100)
    assert "omitted" in compacted


def test_compact_transcript_preserves_commands_and_final_answer():
    transcript = (
        "USER: explain\n"
        + ("noise\n" * 3000)
        + "COMMAND: pytest -q\n"
        + ("more noise\n" * 1000)
        + "ASSISTANT: final answer"
    )

    compacted = _compact_transcript(transcript, max_chars=4000)

    assert compacted.startswith("USER: explain")
    assert "COMMAND: pytest -q" in compacted
    assert compacted.endswith("ASSISTANT: final answer")
