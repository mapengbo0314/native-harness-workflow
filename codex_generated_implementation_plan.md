# Codex-Generated Implementation Plan: Claude-First Harness Generator Overhaul

> Status: Draft ready for implementation planning
> Date: 2026-05-24
> Replaces: none. This file intentionally does not mutate `implementation_plan.md`.
> Primary goal: turn `src/harness` into a Claude Code-first minting engine that generates a valid, testable, observable agentic harness plugin with deterministic hooks, shared state, and Langfuse-backed evals.

---

## 0. Operating Thesis

The project is in an early revamp phase, so the correct target is not a polished multi-platform framework yet. The correct target is a narrow, hardened Claude Code path that proves the architecture with tests and evals.

The minting engine should stop treating harness generation as "copy markdown into a tool folder." It should mint a working control plane:

- A valid Claude Code plugin package.
- A single deterministic state store.
- Hook scripts that enforce routing and safety policy.
- Contract verification that is external to the main model.
- Langfuse traces and eval datasets so each revamp can be measured.
- Compatibility adapters only after the Claude path is stable.

This plan prioritizes Claude Code because Claude plugins can package skills, agents, hooks, MCP servers, LSP servers, monitors, and plugin-local settings. That is the richest execution surface currently relevant to this project.

---

## 1. Docs-Verified Assumptions

These assumptions should be treated as implementation constraints. Re-check the docs before implementing any behavior that depends on CLI or hook schema details.

### 1.1 Claude Code Plugin Facts

Source: https://code.claude.com/docs/en/plugins

- A plugin is a directory with `.claude-plugin/plugin.json` plus component directories at the plugin root.
- `skills/`, `commands/`, `agents/`, `hooks/`, `.mcp.json`, `.lsp.json`, and `monitors/` belong at the plugin root, not inside `.claude-plugin/`.
- Plugins are best for reusable/team/versioned behavior; standalone `.claude/` config is best for quick project-only iteration.
- Local plugin development should support `claude --plugin-dir ./my-plugin` and `/reload-plugins`.
- Plugin `settings.json` currently supports limited keys. Do not assume arbitrary Claude settings can be shipped by plugin settings.

### 1.2 Claude Code Hook Facts

Sources:

- https://code.claude.com/docs/en/hooks
- https://code.claude.com/docs/en/hooks-guide

- Command hooks receive event input as JSON on stdin.
- `exit 2` is the blocking signal for most enforceable hook events.
- Do not combine `exit 2` with structured JSON output. Claude ignores JSON when the hook exits 2.
- `PreToolUse` can block tool calls before they run.
- `PostToolUse` observes completed tool calls but cannot prevent them.
- `Stop` can prevent Claude from stopping and continue the conversation.
- `PreCompact` can block compaction; `PostCompact` cannot.
- `ConfigChange` can block project/user/local settings changes, except managed policy settings.
- `UserPromptSubmit` can block prompt processing; stdout can inject context for prompt/session style hooks, but blocking user prompts should be used carefully because it erases prompt processing.
- Current docs expose tool inputs through hook JSON. Do not assume undocumented fields such as `remainingTokens` exist unless validated locally.

### 1.3 Langfuse Facts

Sources:

- https://langfuse.com/docs/observability/sdk/overview
- https://langfuse.com/docs/evaluation/experiments/datasets
- https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk
- https://langfuse.com/docs/evaluation/evaluation-methods/custom-scores

- Use the current Langfuse Python SDK for new Python work.
- Langfuse SDKs are OpenTelemetry-based and async by default.
- Short-lived scripts and hooks must call `flush()` before exit when telemetry matters.
- Datasets are the right primitive for repeatable eval cases with inputs and expected outputs.
- Experiments should use unique run names so new runs are visible and comparable.
- Scores can be added programmatically for routing correctness, guardrail correctness, verification quality, latency, and token/cost proxies.

---

## 2. Non-Negotiable Design Constraints

- Claude-first: Claude Code plugin generation is the reference implementation.
- Measurable: every meaningful behavior has a deterministic test or Langfuse eval case.
- Stateful but safe: all state writes are atomic.
- JSON-first: hooks parse stdin as strict JSON and reject malformed inputs with capped diagnostics.
- No prompt bloat: large markdown is not recursively inlined into every prompt.
- No hidden cross-root references: plugin assets must work after Claude copies or loads the plugin from its own plugin directory.
- Least surprise: generated files should be explicit and inspectable.
- Compatibility later: Gemini, Codex, Cursor, and other platform paths should become adapters after the Claude plugin path stabilizes.

---

## 3. Target End State

After this overhaul, running the harness init flow for Claude with plugin mode enabled should generate:

```text
.claude/
  plugin-generated/
    .claude-plugin/
      plugin.json
    README.md
    settings.json
    skills/
      <selected-skill>/SKILL.md
    agents/
      orchestrator.md
      planner.md
      implementer.md
      verifier.md
      reviewer.md
      ...
    hooks/
      hooks.json
      prompt_classifier.py
      pre_tool_guard.py
      config_change_guard.py
      stop_verifier.py
      precompact_handoff.py
      post_tool_observer.py
      hook_common.py
    scripts/
      harness_resume.py
      task_tracker.py
      verify_contract.py
      run_langfuse_evals.py
      seed_langfuse_datasets.py
    contracts/
      campaign_state.schema.json
      verification_contract.schema.json
      default_verification_contract.json
    evals/
      routing_cases.jsonl
      guardrail_cases.jsonl
      verification_cases.jsonl
      token_efficiency_cases.jsonl
    state/
      campaign_state.json
```

The exact directory names can change if the Claude docs require a different layout, but the generated plugin must be locally loadable and testable with Claude's plugin development flow.

---

## 4. Implementation Strategy

### Phase 0: Baseline and Stop-the-Bleeding Cleanup

Timeline: 1-2 days

Goal: make the current templates and tests trustworthy before adding new behavior.

#### Tasks

- Clean malformed boilerplate templates in `src/harness/templates/boilerplate/`.
- Remove phantom references to nonexistent agents, rules, and tools.
- Preserve the existing 10+ agent specialization direction, but make every referenced agent resolvable.
- Ensure every `SKILL.md` has valid frontmatter and a clear activation boundary.
- Decide which skills are mandatory core skills and which are stack/domain-selected.
- Add a snapshot test that asserts no generated markdown references nonexistent local files.

#### File Targets

- `src/harness/templates/boilerplate/orchestrator.md`
- `src/harness/templates/boilerplate/agents/*.md`
- `src/harness/templates/boilerplate/skills/*/SKILL.md`
- `src/harness/templates/boilerplate/skills.json` if retained or introduced
- `tests/integration/test_platform_snapshots.py`
- New: `tests/integration/test_template_integrity.py`

#### Acceptance Criteria

- `pytest tests/integration/test_platform_snapshots.py` passes.
- A generated Claude plugin snapshot contains no dangling `@../rules/...` references.
- Every bundled skill either appears in the skills index or is intentionally excluded.
- No generated file contains references to removed agents such as `@architect` unless that agent is restored.

---

### Phase 1: Make Claude Plugin Generation the Reference Path

Timeline: 3-5 days

Goal: harden `generate_orchestrator_plugin` into the canonical output path.

#### Current Repo Starting Point

The repo already has:

- `src/harness/plugin_generator.py::generate_orchestrator_plugin`
- `src/harness/plugin_generator.py::generate_plugin_manifest`
- `src/harness/plugin_generator.py::generate_plugin_sources`
- `tests/integration/test_platform_snapshots.py::test_claude_plugin_layout`

This work should evolve those paths instead of creating a second generator.

#### Tasks

- Make Claude plugin generation opt-in but first-class in `python -m harness --init`.
- Ensure the plugin manifest is valid for current Claude Code plugin docs.
- Generate component directories at plugin root, not inside `.claude-plugin/`.
- Generate `hooks/hooks.json` as the single hook registration file.
- Generate plugin-local `README.md` with local dev and validation commands.
- Keep `settings.json` minimal and limited to docs-supported keys.
- Avoid plugin code that assumes it can import or reference files outside plugin root after installation.
- Add a validation command path to generated setup instructions.

#### File Targets

- `src/harness/plugin_generator.py`
- `src/harness/minting_engine.py`
- `src/harness/cli.py`
- `tests/integration/test_platform_snapshots.py`
- New: `tests/integration/test_claude_plugin_contract.py`

#### Acceptance Criteria

- Generated plugin contains `.claude-plugin/plugin.json`.
- Generated plugin contains root-level `skills/`, `agents/`, and `hooks/` when enabled.
- Generated plugin contains no references to source repo paths that will not exist after plugin installation.
- Snapshot tests assert the plugin layout.
- A manual smoke command is documented:

```bash
claude --plugin-dir ./.claude/plugin-generated
```

---

### Phase 2: Unified State Contract

Timeline: 2-3 days

Goal: every hook and script reads/writes one state file through one shared implementation.

#### Tasks

- Add `hook_common.py` with:
  - `resolve_project_root(input_json)`
  - `resolve_plugin_root()`
  - `resolve_state_path(input_json)`
  - `read_json(path, default)`
  - `atomic_write_json(path, data)`
  - `append_event(state, event)`
  - `capped_text(value, max_chars)`
- Generate `contracts/campaign_state.schema.json`.
- Generate initial `state/campaign_state.json`.
- Store state under the plugin or generated harness directory using a deterministic path.
- Do not let every hook reinvent path resolution.

#### State Shape

```json
{
  "schema_version": 1,
  "session": {
    "session_id": null,
    "last_event": null,
    "last_updated_at": null
  },
  "routing": {
    "active_branch": null,
    "classification_confidence": null,
    "last_user_prompt_hash": null
  },
  "task": {
    "current_goal": null,
    "current_step": null,
    "completed_steps": [],
    "blocked_reason": null
  },
  "guardrails": {
    "blocked_tool_calls": 0,
    "last_block_reason": null,
    "consecutive_tool_failures": 0
  },
  "verification": {
    "last_contract": null,
    "last_result": null,
    "last_failure_summary": null
  },
  "telemetry": {
    "langfuse_enabled": false,
    "last_trace_id": null
  }
}
```

#### Acceptance Criteria

- 100 simulated concurrent or interrupted writes do not corrupt JSON.
- All hooks import the same state helpers.
- Tests prove tmp-file replacement is used instead of direct partial writes.

---

### Phase 3: Claude Hook MVP

Timeline: 1 week

Goal: ship a small but real hook system that enforces meaningful behavior.

#### Hook 1: `prompt_classifier.py`

Event: `UserPromptSubmit`

Purpose:

- Classify user prompts into Branch A/B/C/D.
- Write classification to state.
- Add compact context for downstream hooks or routing.

Branch definitions:

- Branch A: architecture/planning/design.
- Branch B: implementation/refactor across multiple files.
- Branch C: verification/debugging/testing.
- Branch D: surgical fast path, single small fix, no planner/verifier needed.

Rules:

- Prefer deterministic keyword and shape heuristics first.
- If an LLM classifier is later used, do not ask for chain-of-thought.
- Output compact labels and reasons only.
- Never block normal prompt processing except for malformed or unsafe harness control prompts.

Tests:

- Dataset-style unit tests for classification.
- Langfuse routing eval mirrors the same cases.

#### Hook 2: `pre_tool_guard.py`

Event: `PreToolUse`

Purpose:

- Parse strict JSON input.
- Enforce write and shell safety before tools run.
- Enforce Branch D fast-path constraints.

Rules:

- Inspect `tool_name` and `tool_input`.
- Guard `Write`, `Edit`, `MultiEdit`, and shell-equivalent tool calls.
- Guard subagent launches using current Claude tool names from hook input. Do not hard-code old `Task("@planner")` language unless verified.
- For Branch D, block planner/verifier subagent escalation unless the user explicitly asks.
- Block edits to harness critical files unless the active task is harness maintenance:
  - `.claude/settings.json`
  - `.claude/settings.local.json`
  - `.claude/plugin-generated/hooks/hooks.json`
  - `.env`
  - generated `campaign_state.json`
- For `Bash`, parse the command conservatively. Block obvious writes to guarded paths.
- Return either:
  - `exit 2` with stderr reason, or
  - structured JSON with `hookSpecificOutput.permissionDecision`.
- Do not mix `exit 2` and JSON output.

Tests:

- Blocked guarded path edits.
- Allowed ordinary source edits.
- Branch D blocks planner/verifier escalation.
- Malformed JSON fails closed with capped stderr.
- Shell command guard catches redirection to protected paths.

#### Hook 3: `config_change_guard.py`

Event: `ConfigChange`

Purpose:

- Protect project/user/local Claude settings from runtime tampering.

Rules:

- Block unexpected changes to project/local settings unless a state flag permits harness maintenance.
- Audit all settings changes to state and Langfuse when enabled.
- Do not claim policy settings can be blocked.

Tests:

- Project settings mutation blocked.
- Policy settings event is logged but not treated as enforceable.

#### Hook 4: `stop_verifier.py`

Event: `Stop`

Purpose:

- Prevent false completion.
- Run deterministic verification before Claude declares work done.

Rules:

- Run `scripts/verify_contract.py`.
- Capture max 100 lines or 10KB of output.
- If verification fails, block stop with a concise failure summary.
- If verification passes, allow stop and update state.
- Flush Langfuse telemetry before exit when enabled.

Tests:

- Passing contract allows stop.
- Failing contract blocks stop.
- Output caps are enforced.

#### Hook 5: `precompact_handoff.py`

Event: `PreCompact`

Purpose:

- Create deterministic handoff before compaction.

Rules:

- Do not depend on undocumented `remainingTokens`.
- Use `PreCompact` as the reliable lifecycle event.
- Write `HANDOFF.md` with:
  - Goal
  - Current Progress
  - What Worked
  - What Did Not Work
  - Next Steps
  - State File Path
- Update state atomically.
- Allow or block compaction based on whether handoff generation succeeded.

Tests:

- Handoff generated from state.
- Failed write blocks compaction with capped reason.

#### Hook 6: `post_tool_observer.py`

Event: `PostToolUse` and `PostToolUseFailure`

Purpose:

- Observe tool outcomes.
- Track failure streaks.
- Emit Langfuse events.

Rules:

- Do not pretend `PostToolUse` can block completed tool calls.
- Use `PostToolUseFailure` to increment `consecutive_tool_failures`.
- If repeated failures require a model-facing correction, use a later enforceable event such as `PostToolBatch` or `Stop`, or return stderr feedback where docs support it.

Tests:

- Failure count increments.
- Success resets failure streak where appropriate.
- Telemetry failures never break hook behavior.

---

### Phase 4: Contract-Based Verification Engine

Timeline: 3-5 days

Goal: verify outcomes with deterministic contracts outside the main model's judgment.

#### Tasks

- Generate `contracts/verification_contract.schema.json`.
- Generate `contracts/default_verification_contract.json`.
- Generate `scripts/verify_contract.py`.
- Support file assertions:
  - exists
  - does_not_exist
  - contains
  - not_contains
  - regex
  - json_path_equals
- Support command assertions:
  - command
  - timeout_seconds
  - max_output_chars
  - expected_exit_code
- Support project-native test discovery:
  - pytest
  - npm test
  - npm run lint
  - cargo test
  - go test
  - user-specified commands

#### Contract Example

```json
{
  "schema_version": 1,
  "checks": [
    {
      "type": "file_exists",
      "path": "src/harness/plugin_generator.py"
    },
    {
      "type": "command",
      "command": "pytest tests/integration/test_platform_snapshots.py",
      "timeout_seconds": 60,
      "expected_exit_code": 0,
      "max_output_chars": 10000
    }
  ]
}
```

#### Acceptance Criteria

- Verification script exits nonzero on failed checks.
- All output is capped.
- `stop_verifier.py` uses the script rather than duplicating verification logic.
- Tests cover each assertion type.

---

### Phase 5: Langfuse Eval Harness Comes Early

Timeline: parallel with Phases 2-4

Goal: create eval scaffolding before large rewrites so the revamp can be measured.

#### Tasks

- Add `scripts/seed_langfuse_datasets.py`.
- Add `scripts/run_langfuse_evals.py`.
- Add local JSONL eval fixtures under `evals/`.
- Make Langfuse optional and environment-gated.
- Never require Langfuse credentials for normal tests.
- In short-lived scripts, call `langfuse.flush()` before exit.
- Give each experiment run a unique name with timestamp and git SHA when available.

#### Required Datasets

Dataset: `harness/routing`

- Input: user prompt.
- Expected output:
  - branch
  - whether planner allowed
  - whether verifier allowed
  - expected reason category

Dataset: `harness/guardrails`

- Input: simulated hook JSON for `PreToolUse`.
- Expected output:
  - allow/deny
  - blocked path category
  - reason category

Dataset: `harness/verification`

- Input: verification contract and temporary project fixture.
- Expected output:
  - pass/fail
  - capped summary category

Dataset: `harness/token_efficiency`

- Input: generated prompt assembly scenario.
- Expected output:
  - max prompt word count
  - excluded context categories
  - required context categories

#### Scores

Record these as Langfuse scores where credentials are available:

- `routing_accuracy`: 0 or 1
- `guardrail_decision_accuracy`: 0 or 1
- `verification_decision_accuracy`: 0 or 1
- `output_cap_compliance`: 0 or 1
- `state_integrity`: 0 or 1
- `prompt_word_count`: numeric
- `latency_ms`: numeric

#### Local Fallback

If `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are not set:

- Run the same eval cases locally.
- Emit JSON summary to `evals/results/latest.json`.
- Do not fail solely because Langfuse is absent.

#### Acceptance Criteria

- Evals run locally without credentials.
- Evals publish to Langfuse when credentials exist.
- Every hook MVP behavior has at least one eval case.
- CI can run local evals with no network.

---

### Phase 6: Prompt Assembly and Context Economy

Timeline: after hook MVP and eval scaffold

Goal: reduce prompt bloat by using branch-specific context and pointers.

#### Tasks

- Update `src/harness/dispatcher.py` to assemble branch-specific prompts.
- Replace recursive markdown expansion with context pointers where safe.
- Generate `skills_index.json` for selected skills.
- Generate `scripts/activate_skill.py` only if Claude plugin skill loading does not already cover the use case.
- Keep branch context minimal:
  - Branch A: architecture rules, planner, reviewer.
  - Branch B: implementation rules, implementer, verifier.
  - Branch C: debugging/testing rules, verifier, linter/reviewer.
  - Branch D: minimal repo instructions, exact file/task context, no planner/verifier by default.

#### Acceptance Criteria

- Prompt word count drops by at least 30% for standard feature tasks compared to baseline.
- Branch D does not include planner/verifier instructions unless explicitly escalated.
- Eval fixture proves required context remains present.

---

### Phase 7: Task Tracker and Handoff Scripts

Timeline: after state and hooks

Goal: move task progress out of prose and into state.

#### Tasks

- Generate `scripts/task_tracker.py`.
- Support:
  - `--set-goal`
  - `--start-step`
  - `--complete-step`
  - `--block`
  - `--sync-current-progress`
  - `--print-summary`
- For `--sync-current-progress`, use compact summaries:
  - `git status --porcelain`
  - `git diff --stat`
  - never raw full diffs
- Generate `scripts/harness_resume.py`.
- `harness_resume.py` reads state and prints a compact resume prompt.

#### Acceptance Criteria

- Tracker updates state atomically.
- Resume script produces a deterministic, capped resume summary.
- Handoff file and resume script agree on current task state.

---

### Phase 8: Compatibility Adapters

Timeline: after Claude reference implementation is stable

Goal: support Gemini/Codex/Cursor without compromising the Claude plugin path.

#### Tasks

- Define a `PlatformAdapter` interface.
- Claude adapter generates plugin-first output.
- Gemini/Codex/Cursor adapters generate only the supported subset.
- Shared concepts:
  - state schema
  - verification contracts
  - eval fixtures
  - task tracker
- Platform-specific concepts:
  - plugin manifest
  - hook registration
  - tool names
  - settings format

#### Acceptance Criteria

- Claude tests remain the reference.
- Non-Claude adapters cannot weaken Claude acceptance criteria.
- Each adapter declares unsupported features explicitly.

---

## 5. Testing Plan

### Unit Tests

- `tests/unit/test_atomic_state.py`
- `tests/unit/test_hook_common.py`
- `tests/unit/test_prompt_classifier.py`
- `tests/unit/test_pre_tool_guard.py`
- `tests/unit/test_config_change_guard.py`
- `tests/unit/test_verify_contract.py`
- `tests/unit/test_langfuse_eval_runner.py`

### Integration Tests

- `tests/integration/test_claude_plugin_contract.py`
- `tests/integration/test_platform_snapshots.py`
- `tests/integration/test_generated_hooks_smoke.py`
- `tests/integration/test_generated_verification_contracts.py`

### Snapshot Tests

Assert generated layout for:

- Claude standalone mode.
- Claude plugin mode.
- Claude plugin mode with selected skills.
- Claude plugin mode with Langfuse eval scaffold.

### Simulation Tests

- 100 forced-exit state writes.
- malformed hook stdin.
- protected file writes through direct edit tools.
- protected file writes through shell redirection.
- stop verifier failure.
- precompact handoff generation.

---

## 6. Security and Safety Rules

- Hooks fail closed for malformed JSON only where blocking is safe and expected.
- Hooks fail open for telemetry errors.
- Hooks cap all stderr/stdout feedback.
- No hook should print secrets.
- Redact environment variables matching:
  - `*_KEY`
  - `*_TOKEN`
  - `*_SECRET`
  - `PASSWORD`
  - `LANGFUSE_SECRET_KEY`
- Do not let generated scripts overwrite `.env`.
- Do not let generated scripts rewrite `.claude/settings.json` except during explicit setup/install flows.
- Store Langfuse credentials only in environment variables, not generated state.

---

## 7. Acceptance Metrics

### Claude Plugin Validity

- 100% generated Claude plugin layouts satisfy local structural tests.
- Generated plugin can be loaded with `claude --plugin-dir` during manual smoke testing.
- No component directories are incorrectly nested under `.claude-plugin/`.

### Routing

- Branch routing eval accuracy >= 90% on the initial local dataset.
- Branch D planner/verifier bypass works on 100% of surgical edit eval cases unless the user explicitly asks for planning/verification.

### Guardrails

- 100% of protected file write attempts are blocked in fixture tests.
- 100% of normal source edit fixture cases are allowed.
- Shell write attempts to protected paths are blocked in fixture tests.

### State Integrity

- 0 corrupted `campaign_state.json` files across 100 simulated interrupted writes.

### Verification

- Failed verification feedback remains under 2,000 characters.
- Verification command output is capped at 100 lines or 10KB.
- Stop verifier blocks incomplete work in fixture tests.

### Token Economy

- Standard feature prompt assembly shows >= 30% reduction in prompt word count versus baseline.
- Branch D prompts exclude planner/verifier context by default.

### Langfuse

- Local eval mode works without credentials.
- Langfuse mode creates unique experiment runs when credentials exist.
- All short-lived telemetry scripts flush before exit.

---

## 8. Implementation Order for Claude

Use this order when handing work to Claude or another coding agent:

1. Fix template integrity and snapshots.
2. Harden Claude plugin layout generation.
3. Add shared state helpers and schema.
4. Add `PreToolUse` guard MVP.
5. Add `Stop` verifier MVP.
6. Add local eval fixtures and runner.
7. Add Langfuse integration behind environment flags.
8. Add prompt classifier and branch-specific prompt assembly.
9. Add `PreCompact` handoff and resume scripts.
10. Add task tracker.
11. Re-run snapshots, unit tests, local evals, and manual plugin smoke.
12. Only then broaden platform adapters.

---

## 9. Known Risks and Required Validation

- Claude hook input field names may evolve. Validate against local Claude Code version before hard-coding `tool_name` or subagent tool shapes.
- Plugin settings support is intentionally limited. Do not ship arbitrary settings in plugin `settings.json`.
- Marketplace-installed plugins may be copied to a cache. Avoid external relative paths from plugin files.
- `remainingTokens` is not a docs-verified hook input. Use `PreCompact`/`PostCompact` lifecycle hooks for compaction handling unless local testing proves more precise telemetry exists.
- Langfuse SDK examples and versions evolve. Pin implementation to the installed SDK major version and document the required minimum.
- Hooks should not become a second agent. Keep hooks deterministic, small, and testable.

---

## 10. Definition of Done

The overhaul is done when:

- Claude plugin mode is the reference path.
- Generated plugin structure matches current Claude docs.
- Core hooks are deterministic and covered by tests.
- State is unified and atomic.
- Verification blocks false completion.
- Langfuse evals exist early and can run with or without credentials.
- Prompt assembly is branch-aware and measurably smaller.
- Compatibility adapters do not dilute the Claude-first architecture.

