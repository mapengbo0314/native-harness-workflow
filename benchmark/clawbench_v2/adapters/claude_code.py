"""Claude Code adapter for harness-bench.

Runs the `claude --print --output-format json` CLI against a task workspace,
supporting multiple harness configuration variants (no_harness, minimal,
full_harness, rtk, full_harness_rtk, ecc).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from clawbench_v2.adapters._harness_setup import prepare_workspace_for_config

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ECC_PLUGIN_DIR = _REPO_ROOT / "benchmark" / ".cache" / "ecc"
from clawbench_v2.adapters.base import BaseAdapter
from clawbench_v2.models import AdapterRunContext, AdapterRunResult

_RTK_SYSTEM_PROMPT = (
    "RTK is active. Prefix every shell command with `rtk` to compress output "
    "(e.g. `rtk git status`, `rtk pytest`, `rtk ls`). "
    "This reduces token consumption 60-90% per command."
)

# Injected for harness configs to prevent the planning/clarification loop that
# terminates the session in non-interactive batch runs.
_BATCH_MODE_PROMPT = (
    "AUTOMATED BENCHMARK: No human operator is present in this session. "
    "Do not ask clarifying questions or request confirmation before starting. "
    "Read the task prompt, infer all requirements from the codebase, and "
    "implement the complete solution immediately in this single response."
)

_RATE_LIMIT_MARKERS = (
    "You've hit your limit",
    "rate limit",
    "usage limit",
    "credit limit",
    "quota exceeded",
)

_CONTEXT_LIMIT_MARKERS = (
    "context length",
    "context window",
    "context_length_exceeded",
    "too long to process",
    "prompt is too long",
    "exceeds the maximum",
)


def parse_claude_json_output(raw: str) -> tuple[str, dict, float]:
    """Parse --output-format json output into (transcript, usage_dict, cost_usd).

    Falls back gracefully if the output is plain text (older CLI versions).
    """
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            transcript = data.get("result", stripped)
            usage = data.get("usage", {})
            cost = float(data.get("total_cost_usd", 0.0))
            return transcript, usage, cost
        except json.JSONDecodeError:
            pass
    return stripped, {}, 0.0


def _parse_json_meta(stdout: str) -> dict:
    stripped = stdout.strip()
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    return {}


def classify_claude_failure(stdout: str, stderr: str, returncode: int) -> dict[str, object]:
    json_meta = _parse_json_meta(stdout)
    is_error: bool = bool(json_meta.get("is_error", False))
    stop_reason: str = str(json_meta.get("stop_reason") or "")

    text = f"{stdout}\n{stderr}".strip()
    lowered = text.lower()

    if is_error or stop_reason == "max_tokens" or any(m.lower() in lowered for m in _CONTEXT_LIMIT_MARKERS):
        return {
            "error_type": "context_limit",
            "retryable": False,
            "message": str(json_meta.get("result") or text.splitlines()[0] or "context limit exceeded"),
        }
    if returncode != 0 and any(marker.lower() in lowered for marker in _RATE_LIMIT_MARKERS):
        return {
            "error_type": "rate_limit",
            "retryable": True,
            "message": text.splitlines()[0] if text else "Claude CLI rate limit",
        }
    if returncode != 0 and not text:
        return {
            "error_type": "empty_cli_failure",
            "retryable": False,
            "message": "Claude CLI exited non-zero without stdout or stderr",
        }
    if returncode != 0:
        return {
            "error_type": "cli_failure",
            "retryable": False,
            "message": text.splitlines()[0] if text else f"Claude CLI exited {returncode}",
        }
    return {}


class ClaudeCodeAdapter(BaseAdapter):
    name = "claude_code"

    def run(self, ctx: AdapterRunContext) -> AdapterRunResult:
        harness_config: str = str(ctx.model_config.get("harness_config", "no_harness"))

        try:
            prepare_workspace_for_config(ctx.workspace, harness_config, provider="claude")
        except Exception as exc:
            return AdapterRunResult(
                ok=False,
                command=[],
                stdout="",
                stderr=f"harness setup failed: {exc}",
                metadata={"harness_config": harness_config, "setup_error": str(exc)},
            )

        command: list[str] = [
            "claude", "--print", "--output-format", "json",
            "--dangerously-skip-permissions",
        ]

        model_override = str(ctx.model_config.get("model") or "").strip()
        if model_override:
            command.extend(["--model", model_override])

        if harness_config in ("full_harness", "full_harness_rtk"):
            plugin_dir = ctx.workspace / ".claude" / "harness-wf-plugin"
            if plugin_dir.exists():
                command.extend(["--plugin-dir", str(plugin_dir)])

        elif harness_config == "ecc":
            if _ECC_PLUGIN_DIR.exists():
                command.extend(["--plugin-dir", str(_ECC_PLUGIN_DIR)])

        if harness_config in ("full_harness", "full_harness_rtk"):
            command.extend(["--append-system-prompt", _BATCH_MODE_PROMPT])

        if harness_config in ("rtk", "full_harness_rtk"):
            command.extend(["--append-system-prompt", _RTK_SYSTEM_PROMPT])

        env = os.environ.copy()
        env.update(ctx.env)

        try:
            prompt_text = Path(ctx.prompt_file).read_text(encoding="utf-8")
        except OSError as exc:
            return AdapterRunResult(
                ok=False,
                command=command,
                stdout="",
                stderr=f"failed to read prompt file {ctx.prompt_file}: {exc}",
                metadata={"harness_config": harness_config},
            )

        if ctx.mode == "dry":
            return AdapterRunResult(
                ok=True,
                command=command,
                stdout="",
                stderr="",
                metadata={"harness_config": harness_config, "dry_run": True},
            )

        try:
            completed = subprocess.run(
                command,
                input=prompt_text,
                cwd=str(ctx.workspace),
                env=env,
                capture_output=True,
                text=True,
                timeout=ctx.timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return AdapterRunResult(
                ok=False,
                command=command,
                stdout="",
                stderr=f"claude timed out after {ctx.timeout_sec}s",
                metadata={"harness_config": harness_config, "timeout": True},
            )

        transcript, usage, cost_usd = parse_claude_json_output(completed.stdout)
        failure = classify_claude_failure(completed.stdout, completed.stderr, completed.returncode)
        _save_transcript(ctx.workspace, transcript)
        stderr = completed.stderr
        if failure and not stderr:
            stderr = str(failure.get("message") or "")
        ok = completed.returncode == 0 and failure.get("error_type") != "context_limit"
        return AdapterRunResult(
            ok=ok,
            command=command,
            stdout=transcript,
            stderr=stderr,
            metadata={
                "returncode": completed.returncode,
                "harness_config": harness_config,
                "usage": usage,
                "total_cost_usd": cost_usd,
                **failure,
            },
        )


def _save_transcript(workspace: Path, transcript: str) -> None:
    try:
        (workspace / ".bench_transcript.txt").write_text(transcript, encoding="utf-8")
    except OSError:
        pass
