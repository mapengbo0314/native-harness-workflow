# Spec: Agentic Harness Testing Redesign

**Status:** Draft
**Date:** 2026-05-22
**Focus:** Headless Lifecycle, Sandbox Hooks & Efficiency Benchmarking

## 1. Goal
Create a high-fidelity, deterministic test suite that verifies the creation, platform-specific layout, and functional integrity of the Agentic Harness, ensuring all hooks trigger correctly and measuring the efficiency gains of the Graph-First strategy.

## 2. Core Pillars

### Pillar 1: Headless Platform Snapshots
Verify the harness layout for each platform (Gemini, Claude, Codex) using a fully automated flow.
- **Action:** Run the minting lifecycle in a "Headless Mode" (e.g., `HARNESS_HEADLESS=1`).
- **Automation:** Use `GEMINI_API_KEY` from `.env` and automate all interactive prompts.
- **Verification:** Compare output against Golden Snapshots and validate `setup_harness.sh` CLI commands.

### Pillar 2: Live Sandbox & Full Hook Triggering
Verify that **ALL** hooks trigger in a live environment.
- **Action:** Open a Claude Sandbox and execute a standard workflow (Prompt -> Tool Use -> Result -> Compaction -> Stop).
- **Verification:**
    - **PromptInterceptor:** Verify `<matrix_route>` injection.
    - **PreToolGuard:** Verify security/TDD rejections.
    - **PostToolMonitor:** Verify state updates after tool execution.
    - **PreCompactMonitor:** Verify persona reminders are injected into the context before compaction.
    - **StopMonitor:** Verify that the "QA Required" gate blocks session exit if `qa_report.md` is missing.

### Pillar 3: Robust State & Hook Logic Validation
Functional verification of hook side-effects and state transitions.
- **Action:** Overhaul `hook_validator.py` to simulate complex sequences for all hooks.
- **Verification:**
    - **TDD State:** Verify `tdd_status` transitions (None -> Red -> Green).
    - **Escalation Logic:** Verify `[ESCALATION]` triggers after 3 tool rejections.
    - **Hook Integration:** Ensure `PostToolMonitor` correctly seeds the data that `PreCompactMonitor` later uses.

### Pillar 4: Efficiency & CodeGraph Benchmarking
Measure token utilization and verify the "Graph-First" mandate.
- **Action:** Run two parallel subagent tasks in a sandbox.
    - **Scenario A (Graph-First):** CodeGraph MCP enabled.
    - **Scenario B (Fallback):** CodeGraph MCP disabled (forces `grep`/`read_file` usage).
- **Verification:**
    - **Token Utilization:** Compare total tokens consumed in A vs B. Expect >30% reduction in A.
    - **Mandate Enforcement:** Verify that Scenario B triggers `[EFFICIENCY VIOLATION]` warnings from `pre_tool_guard.py` when excessive `grep` is used without Graph context.

## 3. Directory Structure
```text
tests/
├── unit/                       # Fast component logic
├── integration/                # Headless snapshots per platform
├── benchmarks/                 # Token utilization & Graph-First efficiency
├── hooks/                      # Functional tests for ALL generated hooks
└── fixtures/
    ├── boilerplates/           # Sample input projects
    └── snapshots/              # Expected "Golden" outputs
```

## 4. Success Criteria
1. `pytest` runs the lifecycle end-to-end without user input.
2. Sandbox logs confirm all discovered hooks (UPS, PreTool, PostTool, etc.) triggered correctly.
3. Benchmark report proves token savings when using CodeGraph MCP.
4. `hook_validator` confirms state transitions and rejection escalation for the full suite.
 PreTool, PostTool, PreCompact, Stop) triggered correctly.
3. Benchmark report proves token savings when using CodeGraph MCP.
4. `hook_validator` confirms state transitions and rejection escalation for the full suite.
