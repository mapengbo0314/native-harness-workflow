from __future__ import annotations

from benchmark.clawbench_v2.adapters.codex import classify_codex_failure


def test_codex_rate_limit_is_classified() -> None:
    failure = classify_codex_failure("", "rate limit exceeded; try again later", 1)

    assert failure["error_type"] == "rate_limit"
    assert failure["retryable"] is True


def test_codex_context_limit_is_classified_even_with_zero_exit() -> None:
    failure = classify_codex_failure(
        '{"type":"error","message":"context length exceeded"}',
        "",
        0,
    )

    assert failure["error_type"] == "context_limit"
    assert failure["retryable"] is False


def test_codex_empty_nonzero_exit_is_classified() -> None:
    failure = classify_codex_failure("", "", 1)

    assert failure["error_type"] == "empty_cli_failure"
    assert failure["retryable"] is False


def test_codex_context_words_in_normal_transcript_are_not_failures() -> None:
    failure = classify_codex_failure(
        '{"type":"thread.started","thread_id":"t"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"Read the context window docs."}}\n'
        '{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}\n',
        "",
        0,
    )

    assert failure == {}


def test_codex_hook_trust_warning_is_not_a_failure() -> None:
    failure = classify_codex_failure(
        '{"type":"item.completed","item":{"type":"error","message":"`--dangerously-bypass-hook-trust` is enabled."}}\n',
        "",
        0,
    )

    assert failure == {}
