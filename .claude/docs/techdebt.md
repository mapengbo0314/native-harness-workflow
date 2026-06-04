# Tech Debt

Running ledger of known gaps and deferred work. Each entry: what, why it's deferred, and what "done" looks like.

## Harness home anchor not generated for non-Claude platforms

**Source:** `2026-06-03-agents-md-deprecation` — the harness-home anchor was switched from `AGENTS.md` to `.harness-meta.json` (`src/harness/runtime/dispatcher.py`, `evaluate_artifacts`).

**Gap:** `.harness-meta.json` is only written by `generate_orchestrator_plugin`, which is invoked solely from `src/harness/adapters/claude.py`. For the **gemini / codex / cursor / agents** platforms no `.harness-meta.json` is produced. Previously every platform minted `AGENTS.md`, so the old upward-traversal anchor worked everywhere. Now on non-Claude platforms the dispatcher finds neither file and silently falls through to the fragile `config_dir.parent.parent` fallback.

**Why deferred:** Only the Claude platform is in active use right now, so this is not a live regression. (`.gemini/src/dispatcher.py` is also still on the old `AGENTS.md` anchor and is intentionally left as-is — Gemini's deployment differs.)

**Done looks like:** either confirm non-Claude platforms never run this dispatcher, or give all adapters a universal anchor (seed `.harness-meta.json` for every platform, or anchor on a file that already exists everywhere such as `settings.json` / `agent.json`).

## E2E lifecycle tests skipped

**Source:** pre-existing, surfaced during `2026-06-03-agents-md-deprecation` review.

**Gap:** `tests/e2e/test_transactional_minting.py` and `tests/e2e/test_full_harness_lifecycle.py` are `@pytest.mark.skip`'d ("Broken due to cli.py changes"). They were edited to drop `AGENTS.md` assertions but do not execute. AGENTS.md-deprecation coverage currently rests entirely on `tests/integration/test_headless_generation.py` (which does assert AGENTS.md absence across all platforms).

**Why deferred:** the skips are caused by unrelated `cli.py` changes, out of scope for the deprecation work.

**Done looks like:** unbreak the `cli.py` flow these tests exercise and remove the skip markers.
