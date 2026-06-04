# Progress: AGENTS.md Deprecation

**Status:** Complete
**Design:** `.claude/docs/designs/2026-06-03-agents-md-deprecation-design.md`

## 1. Idempotent Injection (`minting_engine.py`)

- [x] Remove hardcoded "Please read .../AGENTS.md" pointer generation.
- [x] Implement regex/string replacement to idempotently inject `<!-- harness:start --> ... <!-- harness:end -->` block into platform files.
- [x] Remove Codex `AGENTS.md` generation branch.

## 2. Update Harness Home Anchor (`dispatcher.py`)

- [x] Change the anchor in `evaluate_artifacts` from `AGENTS.md` to `.harness-meta.json`.

## 3. Test Suites Updates

- [x] Remove `AGENTS.md` assertions from `tests/e2e/test_full_harness_lifecycle.py`.
- [x] Remove `AGENTS.md` assertions from `tests/e2e/test_transactional_minting.py`.
- [x] Remove `AGENTS.md` assertions from `tests/integration/test_headless_generation.py`.
- [x] Remove `AGENTS.md` assertions from `tests/integration/test_platform_snapshots.py`.
- [x] Ensure tests check for `.harness-meta.json` or the appended `CLAUDE.md` block instead.

## Current Blockers

### Review / Query Checklist
- [x] Severity taxonomy
- [x] Impact / Regression
- [x] Reproducibility
- [x] Confidence

### Findings (all resolved)
- [High] [Minting Engine] `src/harness/templates/boilerplate/AGENTS.md` was not deleted. Because the minting engine uses `shutil.copytree` to copy the entire `boilerplate` directory, `AGENTS.md` is still being minted to every generated harness directory (e.g., `.claude/AGENTS.md`). This directly violates the spec to "Cease Minting AGENTS.md". — **Fixed** in `cd76490` (boilerplate file deleted).
- [Medium] [Skills] Boilerplate skills (`src/harness/templates/boilerplate/skills/harness-dispatching-parallel-agents/SKILL.md`, `harness-subagent-driven-development/SKILL.md`, `using-harness-superpowers/SKILL.md`) contain hardcoded references instructing the AI to read or use `AGENTS.md`. These will cause agent failures in new workspaces since `AGENTS.md` will no longer exist. — **Fixed** in `cd76490` (skill references scrubbed).
- [Low] [Test Suite] The tests removed the assertion `assert (temp_project / ... / "AGENTS.md").exists()` but failed to add a negative assertion `assert not (temp_project / ... / "AGENTS.md").exists()`. As a result, the tests pass even though the file is still erroneously minted. — **Fixed** in `f97fbaa` (negative assertion added in `test_headless_generation.py`, runs across all platforms).
- [Low] [Test Suite] `tests/fixtures/snapshots/claude/CLAUDE.md.txt` still contains the legacy "Please read .claude/AGENTS.md" prose and wasn't updated to the new idempotent injection format. — **Fixed** (orphaned fixture removed; the active snapshot is `claude_plugin/CLAUDE.md.txt`).

### Deferred (tracked in `.claude/docs/techdebt.md`)
- Harness-home anchor (`.harness-meta.json`) is only generated for the Claude platform; non-Claude platforms fall back to a fragile path guess.
- E2E lifecycle tests remain `@pytest.mark.skip`'d due to unrelated `cli.py` breakage.
