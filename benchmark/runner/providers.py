"""CLI provider adapters for benchmark agents and judges."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path


SUPPORTED_PROVIDERS = ("claude", "codex")


@dataclass
class TokenUsage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0

    def add(self, other: "TokenUsage") -> None:
        self.input_tokens += other.input_tokens
        self.cached_input_tokens += other.cached_input_tokens
        self.output_tokens += other.output_tokens
        self.reasoning_output_tokens += other.reasoning_output_tokens

    def as_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "uncached_input_tokens": max(
                0, self.input_tokens - self.cached_input_tokens
            ),
            "output_tokens": self.output_tokens,
            "reasoning_output_tokens": self.reasoning_output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
        }


@dataclass
class ProviderTurnResult:
    transcript: str
    session_id: str | None = None
    error: str | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)


@dataclass
class ProviderJudgeResult:
    text: str
    usage: TokenUsage = field(default_factory=TokenUsage)


def run_agent_turn(
    provider: str,
    prompt: str,
    project: Path,
    timeout: int,
    session_id: str | None = None,
    plugin_dir: Path | None = None,
    system_prompt: str | None = None,
    env: dict[str, str] | None = None,
) -> ProviderTurnResult:
    if provider == "claude":
        return _run_claude_turn(
            prompt, project, timeout, session_id, plugin_dir, system_prompt, env
        )
    if provider == "codex":
        return _run_codex_turn(
            prompt, project, timeout, session_id, system_prompt, env
        )
    raise ValueError(f"Unsupported provider: {provider}")


def run_judge(provider: str, prompt: str, timeout: int = 60) -> ProviderJudgeResult:
    if provider == "claude":
        result = subprocess.run(
            ["claude", "--print", "--output-format", "json", "--dangerously-skip-permissions"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        _check_result(result, "Claude judge")
        transcript, usage = _parse_claude_json_output(result.stdout)
        return ProviderJudgeResult(text=transcript, usage=_claude_usage_to_token_usage(usage))

    if provider == "codex":
        command = [
            "codex",
            "exec",
            "--json",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--ignore-rules",
            "-",
        ]
        max_attempts = 5
        result = None
        last_error: str | None = None
        with tempfile.TemporaryDirectory(prefix="harness-bench-judge-") as tmp:
            for attempt in range(max_attempts):
                result = subprocess.run(
                    command,
                    input=prompt,
                    cwd=tmp,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                if result.returncode == 0:
                    last_error = None
                    break
                last_error = _result_error(result) or ""
                if attempt == max_attempts - 1:
                    break
                # Exponential backoff: 2, 4, 8, 16 seconds between the 5 attempts.
                # Add an extra dose of patience when stderr smells like a rate limit
                # — codex returns transient 429s during burst judging.
                backoff = 2 ** (attempt + 1)
                if _looks_like_rate_limit(last_error):
                    backoff *= 2
                time.sleep(backoff)
        if result is None or result.returncode != 0:
            # Final failure — raise rather than returning junk zeros so the
            # caller (scorer._judge_criteria) records a judge_failed scenario
            # instead of silently scoring criteria as failed.
            raise RuntimeError(
                f"Codex judge failed after {max_attempts} attempts: "
                f"{last_error or 'unknown error'}"
            )
        _, transcript, usage = _parse_codex_jsonl(result.stdout)
        return ProviderJudgeResult(text=transcript.strip(), usage=usage)

    raise ValueError(f"Unsupported provider: {provider}")


def _run_claude_turn(
    prompt: str,
    project: Path,
    timeout: int,
    session_id: str | None,
    plugin_dir: Path | None,
    system_prompt: str | None,
    env: dict[str, str] | None,
) -> ProviderTurnResult:
    command = ["claude", "--print", "--output-format", "json", "--dangerously-skip-permissions"]
    if plugin_dir and plugin_dir.exists():
        command.extend(["--plugin-dir", str(plugin_dir)])
    if system_prompt:
        command.extend(["--append-system-prompt", system_prompt])
    if session_id:
        command.append("--continue")

    result = subprocess.run(
        command,
        input=prompt,
        cwd=project,
        env=env or os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    error = _result_error(result)
    transcript, usage = _parse_claude_json_output(result.stdout)
    return ProviderTurnResult(
        transcript=transcript,
        session_id=session_id or "continue-by-cwd",
        error=error,
        usage=_claude_usage_to_token_usage(usage),
    )


def _run_codex_turn(
    prompt: str,
    project: Path,
    timeout: int,
    session_id: str | None,
    system_prompt: str | None,
    env: dict[str, str] | None,
) -> ProviderTurnResult:
    effective_prompt = prompt
    if system_prompt and not session_id:
        effective_prompt = f"{system_prompt}\n\n{prompt}"

    common = [
        "--json",
        "--dangerously-bypass-approvals-and-sandbox",
        "--dangerously-bypass-hook-trust",
    ]
    if session_id:
        command = ["codex", "exec", "resume", *common, session_id, "-"]
    else:
        command = ["codex", "exec", *common, "-C", str(project), "-"]

    result = subprocess.run(
        command,
        input=effective_prompt,
        cwd=project,
        env=env or os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    thread_id, transcript, usage = _parse_codex_jsonl(result.stdout)
    return ProviderTurnResult(
        transcript=transcript,
        session_id=thread_id or session_id,
        error=_result_error(result),
        usage=usage,
    )


def _parse_claude_json_output(raw: str) -> tuple[str, dict]:
    """Parse --output-format json output into (transcript, usage_dict)."""
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            return data.get("result", stripped), data.get("usage", {})
        except json.JSONDecodeError:
            pass
    return stripped, {}


def _claude_usage_to_token_usage(usage: dict) -> TokenUsage:
    return TokenUsage(
        input_tokens=int(usage.get("input_tokens", 0)),
        cached_input_tokens=int(usage.get("cache_read_input_tokens", 0)),
        output_tokens=int(usage.get("output_tokens", 0)),
    )


def _parse_codex_jsonl(output: str) -> tuple[str | None, str, TokenUsage]:
    thread_id = None
    transcript_parts = []
    usage = TokenUsage()

    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            if line.strip():
                transcript_parts.append(line.strip())
            continue

        if event.get("type") == "thread.started":
            thread_id = event.get("thread_id") or thread_id
            continue
        if event.get("type") == "turn.completed":
            turn_usage = event.get("usage", {})
            usage.add(TokenUsage(
                input_tokens=int(turn_usage.get("input_tokens", 0)),
                cached_input_tokens=int(turn_usage.get("cached_input_tokens", 0)),
                output_tokens=int(turn_usage.get("output_tokens", 0)),
                reasoning_output_tokens=int(
                    turn_usage.get("reasoning_output_tokens", 0)
                ),
            ))
            continue
        if event.get("type") != "item.completed":
            continue

        item = event.get("item", {})
        item_type = item.get("type", "item")
        if item_type == "agent_message" and item.get("text"):
            transcript_parts.append(f"ASSISTANT: {item['text']}")
        elif item_type == "command_execution":
            command = item.get("command", "")
            output_text = _compact_command_output(
                item.get("aggregated_output", "")
            )
            transcript_parts.append(
                f"COMMAND: {command}\nOUTPUT:\n{output_text}".strip()
            )
        elif item_type == "error" and item.get("message"):
            transcript_parts.append(f"ERROR: {item['message']}")

    return thread_id, "\n\n".join(transcript_parts), usage


def _compact_command_output(output: str, max_chars: int = 1200) -> str:
    if len(output) <= max_chars:
        return output
    head = max_chars // 2
    tail = max_chars - head
    omitted = len(output) - max_chars
    return (
        f"{output[:head]}\n"
        f"... [{omitted:,} command-output characters omitted] ...\n"
        f"{output[-tail:]}"
    )


def _result_error(result: subprocess.CompletedProcess[str]) -> str | None:
    if result.returncode == 0:
        return None
    stderr = result.stderr.strip()
    return stderr or f"process exited with status {result.returncode}"


_RATE_LIMIT_NEEDLES = (
    "rate limit",
    "rate_limit",
    "ratelimit",
    "429",
    "too many requests",
    "quota",
    "throttle",
)


def _looks_like_rate_limit(stderr: str) -> bool:
    """Best-effort detection of rate-limit / throttling messages in stderr."""
    if not stderr:
        return False
    lowered = stderr.lower()
    return any(needle in lowered for needle in _RATE_LIMIT_NEEDLES)


def _check_result(result: subprocess.CompletedProcess[str], label: str) -> None:
    error = _result_error(result)
    if error:
        raise RuntimeError(f"{label} failed: {error}")
