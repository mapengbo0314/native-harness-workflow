# Task Progress: Claude-First Harness Generator Overhaul

Based on `implementation_plan.md`.

Verification note: phases 0, 1, 2, and 3 were checked against the current repo state and focused tests on 2026-05-24.

## Phase 0: Baseline and Stop-the-Bleeding Cleanup
**Goal:** make the current templates and tests trustworthy before adding new behavior.
- [x] Clean malformed boilerplate templates in `src/harness/templates/boilerplate/`.
- [x] Remove phantom references to nonexistent agents, rules, and tools.
- [x] Preserve existing 10+ agent specialization direction; make every referenced agent resolvable.
- [x] Ensure every `SKILL.md` has valid frontmatter and a clear activation boundary.
- [x] Add snapshot test that asserts no generated markdown references nonexistent local files.
- [x] Acceptance: `pytest tests/integration/test_platform_snapshots.py` passes.
- [x] Acceptance: `pytest tests/integration/test_template_integrity.py` passes (no dangling `@../rules/...` references).

## Phase 1: Make Claude Plugin Generation the Reference Path
**Goal:** harden `generate_orchestrator_plugin` into the canonical output path.
- [x] Make Claude plugin generation opt-in but first-class in `python -m harness --init`.
- [x] Ensure the plugin manifest is valid for current Claude Code plugin docs.
- [x] Generate component directories at plugin root.
- [x] Generate `hooks/hooks.json` as the single hook registration file.
- [x] Generate plugin-local `README.md`.
- [x] Update `tests/integration/test_platform_snapshots.py` and add `test_claude_plugin_contract.py`.
- [x] Acceptance: Plugin layout snapshot matches docs.

## Phase 2: Unified State Contract
**Goal:** every hook and script reads/writes one state file through one shared implementation.
- [x] Add `hook_common.py` (with `resolve_state_path`, `atomic_write_json`, etc.).
- [x] Generate `contracts/campaign_state.schema.json`.
- [x] Generate initial `state/campaign_state.json`.
- [x] Acceptance: Unit tests prove `atomic_write_json` handles concurrency without corruption.

## Phase 2.1: Claude Hook MVP
**Goal:** ship a small but real hook system that enforces meaningful behavior.
- [x] Hook 1: `prompt_classifier.py` (UserPromptSubmit)
- [x] Hook 2: `pre_tool_guard.py` (PreToolUse)
- [x] Hook 3: `config_change_guard.py` (ConfigChange)
- [x] Hook 4: `stop_verifier.py` (Stop)
- [x] Hook 5: `precompact_handoff.py` (PreCompact)
- [x] Hook 6: `post_tool_observer.py` (PostToolUse / PostToolUseFailure)
- [x] Update minting engine to write these to `.claude/plugin-generated/hooks/`.
- [x] Acceptance: Unit tests pass for all hook logics using mock JSON.
- [x] **STOP AND WAIT FOR HUMAN:** Manual testing with `claude --plugin-dir` required after this point.

## Phase 2.2: Claude Plugin Stabilization and Standards Lock
**Goal:** eliminate legacy split-brain plugin generation and make the Claude plugin pass current official Claude Code plugin, hook, and install standards before proceeding.

- [x] Remove legacy `src/hooks/` generation from `plugin_generator.py`; the generated plugin must use only root-level `hooks/`.
- [x] Reduce `plugin_generator.py` to a thin packager that copies the canonical boilerplate plugin assets and writes only standards-compatible metadata.
- [x] Remove ignored/nonstandard manifest fields such as `tools` and `entry_point`; `claude plugin validate --strict` must pass.
- [x] Update `hooks/hooks.json` commands to execute plugin-root scripts via `${CLAUDE_PLUGIN_ROOT}` instead of cwd/PYTHONPATH-dependent module commands.
- [x] Replace naive protected-path substring checks in `pre_tool_guard.py` with normalized project-relative path resolution and exact file/directory matching.
- [x] Add guardrail bypass/regression tests for `.env`, safe names like `venv/config.py`, doubled slashes, `../` traversal, absolute paths, and protected hook/settings files.
- [x] Replace the legacy generated hook validator with tests that parse `hooks/hooks.json` and execute the exact registered hook commands with official Claude hook payloads.
- [x] Add plugin contract tests that assert no generated `.claude/plugin-generated/src/hooks/` directory exists.
- [x] Add local marketplace/install readiness tests for generated plugin metadata instead of relying only on `claude --plugin-dir`.
- [x] Refresh stale Claude plugin snapshots only after strict validation and runtime hook-command tests pass.
- [x] Enforce strict `exit 2` blocking protocol and global try/except fail-safes across all hook scripts.
- [x] Implement Circuit Breaker logic (`consecutive_tool_failures`) in state and hooks to prevent doom loops.
- [x] Acceptance: `claude plugin validate <generated-plugin> --strict` passes with zero warnings.
- [x] Acceptance: focused plugin, hook, minting, and snapshot tests pass.
- [x] **STOP AND WAIT FOR HUMAN:** Manual Claude Code smoke test required with both `claude --plugin-dir` and documented marketplace/install flow before Phase 4 begins.

## Phase 3: The Contract-Based Verification Engine
**Goal:** verify outcomes with deterministic contracts outside the main model's judgment.
- [x] Generate `contracts/verification_contract.schema.json`.
- [x] Generate `contracts/default_verification_contract.json`.
- [x] Generate `scripts/verify_contract.py`.
- [x] Support file assertions (exists, does_not_exist, contains, regex, etc.).
- [x] Support command assertions.
- [x] Acceptance: Verification script exits nonzero on failed checks and caps output. `stop_verifier.py` integrates it.

## Phase 4: Observability & Langfuse Integration
**Goal:** create eval scaffolding before large rewrites so the revamp can be measured.
- [x] Add `langfuse` and `python-dotenv` to project dependencies.
- [x] Install the Langfuse AI skill from github.com/langfuse/skills.
- [x] Use the Langfuse skill to add tracing to the application following best practices.
- [x] Ensure environment variables are explicitly propagated to subprocesses for portable telemetry collection across minted harnesses.
- [x] Add `scripts/seed_langfuse_datasets.py`.
- [x] Add `scripts/run_langfuse_evals.py`.
- [x] Add local JSONL eval fixtures under `evals/`.
- [x] Support local JSON summary fallback if Langfuse credentials are not set.
- [x] Acceptance: Evals run locally without credentials and publish to Langfuse when set.

## Phase 5: Prompt Assembly and Context Economy
**Goal:** reduce prompt bloat by using branch-specific context and pointers.
- [ ] Update `src/harness/dispatcher.py` to assemble branch-specific prompts.
- [ ] Replace recursive markdown expansion with context pointers where safe.
- [ ] Generate `skills_index.json` for selected skills.
- [ ] Generate `scripts/activate_skill.py`.
- [ ] Acceptance: Prompt word count drops by >= 30% for standard features.

## Phase 6: Task Tracker and Handoff Scripts
**Goal:** move task progress out of prose and into state.
- [ ] Generate `scripts/task_tracker.py` (with flags like `--set-goal`, `--complete-step`).
- [ ] Generate `scripts/harness_resume.py`.
- [ ] Acceptance: Tracker updates state atomically; resume script uses deterministic, capped summaries.

## Phase 7: Compatibility Adapters
**Goal:** support Gemini/Codex/Cursor without compromising the Claude plugin path.
- [ ] Define a `PlatformAdapter` interface.
- [ ] Claude adapter generates plugin-first output.
- [ ] Gemini/Codex/Cursor adapters generate supported subsets.
- [ ] Acceptance: Non-Claude adapters explicitly declare unsupported features without weakening Claude acceptance criteria.
