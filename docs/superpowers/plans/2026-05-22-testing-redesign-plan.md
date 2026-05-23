# Implementation Plan: Agentic Harness Testing Strategy Redesign

This plan outlines the steps to implement a robust, deterministic testing strategy for the Agentic Harness, focusing on headless lifecycle automation, platform-specific snapshotting, and hook side-effect validation.

## Context
The current testing suite is minimal and requires manual intervention for the lifecycle discovery and minting phases. This redesign will automate the end-to-end flow and provide high-fidelity verification of the harness's behavioral mandates (Graph-First, TDD, Verification Gate).

## Design Doc

### Problem Statement
- **Manual Toil**: Initializing the harness requires interactive CLI input, blocking CI/CD integration.
- **Snapshot Drift**: No automated verification that the minted harness layout matches platform expectations (Gemini, Claude, Codex).
- **Invisible Side-Effects**: Hooks (UPS, PreTool, Stop) are not functionally tested for state transitions and rejections.
- **Efficiency Blindness**: No empirical data to prove that the CodeGraph strategy actually reduces token usage or improves tool selection.

### Proposed Design
1.  **Headless Mode**: Introduce `HARNESS_HEADLESS=1` to bypass all CLI `input()` prompts with sensible defaults or env-provided values.
2.  **Platform Snapshot Suite**: Integration tests that mint a harness and compare the file structure and key content against "Golden Snapshots".
3.  **Functional Hook Testing**: Overhaul `hook_validator.py` to simulate complex agent sessions and assert on `consecutive_rejections`, `tdd_status`, and `matrix_route` injection.
4.  **Sandbox Benchmarking**: A dedicated test suite that measures token utilization and tool counts across different discovery strategies.

### Alternatives
- **Unit Testing Only**: Rejected because the primary value of the harness is the integration of multiple components (Boilerplate + Logic + LLM + Hooks).
- **Actual LLM Calls in CI**: Rejected for cost/latency, but used for one-off "Smoke Tests". We prefer Mock/Simulated LLM for primary CI.

### Sphinch Marks
- [ ] `HARNESS_HEADLESS=1` allows `harness-wf init` to complete without user input.
- [ ] `tests/integration/test_platform_snapshots.py` passes for Gemini, Claude, and Codex.
- [ ] `hook_validator.py` successfully detects and blocks a dangerous command (e.g., `rm -rf`).
- [ ] `StopMonitor` correctly exits with non-zero code if `artifacts/qa_report.md` is missing after implementation.
- [ ] `test_efficiency.py` generates a report file in `artifacts/benchmarks/`.

## Plan

### 1. Headless Infrastructure & Lifecycle Automation
- [ ] **Task 1.1**: Update `src/harness/cli.py` to respect `HARNESS_HEADLESS=1`.
    - Provide defaults for "purpose", "vocab", "invariants", and "platform selection" when headless.
- [ ] **Task 1.2**: Update `src/harness/minting_engine.py`'s `wait_for_user_review_and_read_domain` to bypass the prompt if `HARNESS_HEADLESS=1`.
- [ ] **Task 1.3**: Create `tests/fixtures/boilerplates/sample-py-app/` to serve as a standardized input project for tests.

### 2. Platform Snapshots & Integration
- [ ] **Task 2.1**: Implement `tests/integration/test_platform_snapshots.py`.
    - Setup: Create a temp directory with `sample-py-app`.
    - Action: Run minting for platform X.
    - Verification: Assert `GEMINI.md` (for Gemini), `CLAUDE.md` + `.claude/plugin-generated/` (for Claude), and `AGENTS.md` (for Codex) exist and contain expected sections.
- [ ] **Task 2.2**: Generate initial "Golden Snapshots" for all 3 platforms in `tests/fixtures/snapshots/`.

### 3. Functional Hook & State Validation
- [ ] **Task 3.1**: Overhaul `src/harness/plugin_generator.py`'s `hook_validator.py` template.
    - Add mocks for `sys.stdin` and `sys.stdout`.
    - Add tests for `pre_tool_guard.py` (Grep-First rejection, TDD rejection, Security rejection).
    - Add tests for `post_tool_monitor.py` (state updates on test success/failure).
- [ ] **Task 3.2**: Implement `tests/hooks/test_hook_logic.py`.
    - Verify that `tdd_status` transitions from `None` -> `red` -> `green` correctly affects `pre_tool_guard`.
    - Verify `consecutive_rejections` triggers `[ESCALATION]` at threshold 3.

### 4. Sandbox Efficiency Benchmarking
- [ ] **Task 4.1**: Implement `tests/benchmarks/test_graph_efficiency.py`.
    - Simulate a sequence of tool calls (Grep vs CodeGraph).
    - Calculate "Mock Tokens" based on payload size.
    - Assert that CodeGraph usage is prioritized by the `pre_tool_guard`.
- [ ] **Task 4.2**: Implement verification logic for `[EFFICIENCY VIOLATION]` warnings when `grep` is overused without CodeGraph.

### 5. Verification Gate Enforcement
- [ ] **Task 5.1**: Test the `stop_monitor.py` logic.
    - Create a test case where implementation has started (`tdd_status` = green) but `artifacts/qa_report.md` is missing.
    - Assert that the hook exits with `1`.

## Verification
- **Unit Tests**: `pytest tests/unit/`
- **Integration Snapshots**: `pytest tests/integration/test_platform_snapshots.py`
- **Hook Functional Tests**: `pytest tests/hooks/`
- **Benchmarking**: `pytest tests/benchmarks/test_graph_efficiency.py`

## Failure Modes
- **Boilerplate Sync**: If the boilerplate files change, snapshots will fail. This is intended; updates must be conscious.
- **Path Resolution**: Relative paths in `hook_validator.py` must be robust to different execution environments.
