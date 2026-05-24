# Harness Generator Overhaul: Implementation Plan

> **Goal**: Upgrade the `src/harness` Python framework into a Minting Engine that generates Claude-first agentic harnesses with structural safety: hooks, unified state, deterministic verification, and measurable execution.
> **Audit Reference**: `harness_audit.md` - 20 gaps identified.

> [!IMPORTANT]
> **Architecture Strategy**: The `src/harness` CLI is a Minting Engine. It should mint executable safety rails and stateful workflow infrastructure rather than relying only on markdown instructions.

---

## Phase 0: Baseline and Stop-the-Bleeding Cleanup
**Status**: Complete
**Goal**: Make the current templates and tests trustworthy before adding new behavior.

### Tasks
- Clean malformed boilerplate templates in `src/harness/templates/boilerplate/`.
- Remove phantom references to nonexistent agents, rules, and tools.
- Preserve the existing 10+ agent specialization direction while making every referenced agent resolvable.
- Ensure every `SKILL.md` has valid frontmatter and a clear activation boundary.
- Add snapshot/integrity coverage for generated markdown references.

### Acceptance
- `pytest tests/integration/test_platform_snapshots.py` passes.
- `pytest tests/integration/test_template_integrity.py` passes.

---

## Phase 1: Make Claude Plugin Generation the Reference Path
**Status**: Complete
**Goal**: Harden `generate_orchestrator_plugin` into the canonical Claude output path.

### Tasks
- Make Claude plugin generation opt-in but first-class in `python -m harness --init`.
- Generate a current Claude Code plugin manifest.
- Generate component directories at the plugin root.
- Generate `hooks/hooks.json` as the single hook registration file.
- Generate plugin-local `README.md`.
- Update snapshot and contract coverage for the Claude plugin layout.

### Acceptance
- Generated plugin layout matches the expected Claude plugin contract.
- `tests/integration/test_claude_plugin_contract.py` covers manifest, hooks, marketplace metadata, and strict validation when `claude` is installed.

---

## Phase 2: Unified State Contract and Claude Hook MVP
**Status**: Complete
**Goal**: Make every hook and script read/write one state file through shared implementation, then ship a small real hook system.

### Tasks
- Add `hook_common.py` with shared state-path resolution, JSON reads, and atomic writes.
- Generate `contracts/campaign_state.schema.json`.
- Generate initial `state/campaign_state.json`.
- Generate Claude hook scripts:
  - `prompt_classifier.py` (`UserPromptSubmit`)
  - `pre_tool_guard.py` (`PreToolUse`)
  - `config_change_guard.py` (`ConfigChange`)
  - `stop_verifier.py` (`Stop`)
  - `precompact_handoff.py` (`PreCompact`)
  - `post_tool_observer.py` (`PostToolUse` / `PostToolUseFailure`)
- Register hooks through plugin-root `hooks/hooks.json`.
- Remove legacy `src/hooks/` generation and use only root-level plugin hooks.
- Execute hook commands via `${CLAUDE_PLUGIN_ROOT}`.
- Harden protected-path checks against traversal, doubled slashes, absolute paths, and safe-name false positives.
- Add marketplace/install readiness coverage.
- Enforce strict `exit 2` blocking protocol and global try/except fail-safes across all hook scripts to ensure the LLM cannot bypass blocks.
- Implement Circuit Breaker logic (`consecutive_tool_failures`) in state and observer hooks to prevent infinite retry loops (doom loops).

### Acceptance
- Unit tests prove `atomic_write_json` handles concurrent writes without corruption.
- Hook tests execute the exact commands registered in `hooks/hooks.json` with Claude-style payloads.
- Generated plugin contains no `.claude/plugin-generated/src/hooks/` directory.
- `claude plugin validate <generated-plugin> --strict` passes with zero warnings when the CLI is available.

### Manual Gate
- Manual Claude Code smoke test required with both `claude --plugin-dir` and documented marketplace/install flow before Phase 4 begins.

---

## Phase 3: The Contract-Based Verification Engine
**Status**: Complete
**Goal**: Verify outcomes with deterministic contracts outside the main model's judgment.

### Tasks
- Generate `contracts/verification_contract.schema.json`.
- Generate `contracts/default_verification_contract.json`.
- Generate `scripts/verify_contract.py`.
- Support file assertions such as `exists`, `does_not_exist`, `contains`, and regex matching.
- Support command assertions.
- Integrate deterministic verification through `stop_verifier.py`.

### Acceptance
- Verification script exits nonzero on failed checks.
- Verification output is capped to protect context.
- Unit coverage proves success, failure, output caps, and Stop hook integration behavior.

---

## Phase 4: Observability and Langfuse Integration
**Status**: Pending
**Goal**: Create eval scaffolding before large rewrites so the revamp can be measured.

### Tasks
- Add `langfuse` and `python-dotenv` to project dependencies (`pyproject.toml` and/or `requirements.txt`).
- Install the Langfuse AI skill from github.com/langfuse/skills.
- Use the Langfuse skill to add tracing to the application following best practices.
- Ensure environment variables (e.g., from `.env`) are explicitly propagated to subprocesses to allow portable telemetry collection across all minted harnesses.
- Add `scripts/seed_langfuse_datasets.py`.
- Add `scripts/run_langfuse_evals.py`.
- Add local JSONL eval fixtures under `evals/`.
- Support local JSON summary fallback when Langfuse credentials are not set.

### Acceptance
- Evals run locally without credentials and publish to Langfuse when credentials are set.

---

## Phase 5: Prompt Assembly and Context Economy
**Status**: Pending
**Goal**: Reduce prompt bloat through branch-specific context and pointers.

### Tasks
- Update `src/harness/dispatcher.py` to assemble branch-specific prompts.
- Replace recursive markdown expansion with context pointers where safe.
- Generate `skills_index.json` for selected skills.
- Generate `scripts/activate_skill.py`.

### Acceptance
- Prompt word count drops by at least 30% for standard feature workflows.

---

## Phase 6: Task Tracker and Handoff Scripts
**Status**: Pending
**Goal**: Move task progress out of prose and into deterministic state.

### Tasks
- Generate `scripts/task_tracker.py` with flags such as `--set-goal` and `--complete-step`.
- Generate `scripts/harness_resume.py`.

### Acceptance
- Tracker updates state atomically.
- Resume script emits deterministic, capped summaries.

---

## Phase 7: Compatibility Adapters
**Status**: Pending
**Goal**: Support Gemini, Codex, and Cursor without compromising the Claude plugin path.

### Tasks
- Define a `PlatformAdapter` interface.
- Keep the Claude adapter plugin-first.
- Add Gemini/Codex/Cursor adapters for supported subsets.

### Acceptance
- Non-Claude adapters explicitly declare unsupported features without weakening Claude acceptance criteria.
