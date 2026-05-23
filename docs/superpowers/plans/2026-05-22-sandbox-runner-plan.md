# Implementation Plan: Live Agent Sandbox Runner

## Problem Statement
The "Agentic Harness" provides a complex orchestration layer (classification, hooks, subagents) that adds overhead to every agent turn. Currently, we lack an automated, empirical way to measure the "cost" (tokens/characters) and "efficiency" (useful work vs. harness overhead) of this system. Developers need a deterministic, headless sandbox to stress-test harness changes and visualize their impact on agent performance.

## Proposed Design
The **Live Agent Sandbox** is a deterministic execution environment that runs a "synthetic turn" using a real LLM but within a controlled, instrumented project.

### 1. Runner Infrastructure (`tests/sandbox/runner.py`)
A standalone Python script that:
- Mints a fresh harness in a temporary directory using the `sample-py-app` boilerplate.
- Executes a "Mock Host" loop that simulates the platform (Claude/Gemini).
- Dispatches a task to a live LLM via the `OrchestratorDispatcher`.
- Implements a "Local Tool Runner" to execute agent tool calls (Read, Edit, etc.) within the sandbox.

### 2. Instrumentation Layer
A new event-logging system integrated into the harness:
- **`src/harness/instrumentation.py`**: A lightweight logger for hook entry/exit, tool payloads, and classification results.
- **Hook Integration**: Boilerplate hooks in `src/harness/templates/boilerplate/` will log to `sandbox_events.json` when `HARNESS_INSTRUMENTATION_FILE` is set.
- **Token Analytics**: The logger will record character counts for every prompt segment (hook-injected vs. user-provided).

### 3. Reporting Dashboard (`artifacts/sandbox_stats.md`)
An automatically generated Markdown report that summarizes the turn:
- **Total Characters**: Cumulative count of all exchanges.
- **Harness Overhead**: Ratio of characters injected by hooks vs. the base agent responses.
- **Routing Accuracy**: Comparison of the Orchestrator's chosen branch vs. the expected branch for the task.
- **Tool Manifest**: frequency and payload size of each tool used.

## Sphinch Marks (Pass/Fail Assertions)
- [ ] `tests/sandbox/runner.py` completes a full "Add Docstring" task headlessly.
- [ ] `sandbox_events.json` captures at least one `HOOK_START` and `HOOK_END` event.
- [ ] `artifacts/sandbox_stats.md` contains a "Efficiency Ratio" metric.
- [ ] The runner correctly detects when the Orchestrator selects a "Branch B" (Planning) vs "Branch D" (Surgical) for different task types.
- [ ] All temporary files are cleaned up after the runner exits (unless `--keep` is passed).

## Alternatives Considered
- **Mock Agents**: Rejected because they don't capture the emergent behavior of how real LLMs respond to hook-injected context.
- **Integration Tests**: Existing integration tests check for *correctness* but don't provide *efficiency analytics*.

---

## Plan

### Phase 1: Infrastructure & Instrumentation
1. **Create `src/harness/instrumentation.py`**:
   - Implement `HarnessEventLogger` to write JSON lines to a file specified by `HARNESS_INSTRUMENTATION_FILE`.
   - Support event types: `HOOK`, `TOOL`, `LLM_PROMPT`, `LLM_RESPONSE`, `CLASSIFICATION`.
2. **Update Boilerplate Hooks**:
   - Modify `src/harness/templates/boilerplate/src/hooks/prompt_interceptor.py`.
   - Modify `src/harness/templates/boilerplate/src/hooks/pre_tool_guard.py`.
   - Modify `src/harness/templates/boilerplate/src/hooks/stop_monitor.py`.
   - Each should log their start, end, and any modifications they make to the prompt/tool.
3. **Verify Logger**: Create a small unit test to ensure hooks log correctly when triggered via subprocess.

### Phase 2: Sandbox Runner & Mock Host
1. **Implement `tests/sandbox/runner.py`**:
   - **Environment Setup**: Use `tempfile.TemporaryDirectory` and `harness.minting_engine.mint_workspace`.
   - **MockHost Class**:
     - Manage conversation history.
     - Use `harness.dispatcher.OrchestratorDispatcher` to classify intent and route the task.
     - Use `harness.discovery_engine.query_llm` to get live agent responses.
   - **Tool Execution Engine**:
     - Map platform-specific tools (e.g., `Bash`, `Edit`, `Read`) to local Python implementations that operate on the sandbox directory.
2. **Handle Branch Scenarios**:
   - Implement a `--scenario` flag (e.g., `docstring`, `bugfix`, `typo`) that sets the initial prompt and the "Expected Branch".

### Phase 3: Analytics & Reporting
1. **Implement Stats Aggregator**:
   - Parse `sandbox_events.json`.
   - Calculate "Harness Tax": Total Hook Characters / Total Prompt Characters.
   - Calculate "Tool Weight": Character counts per tool invocation.
2. **Generate `artifacts/sandbox_stats.md`**:
   - Create a Markdown template.
   - Include a summary table and a "Timeline of Events".

### Phase 4: Validation & Cleanup
1. **Run Full Sandbox Test**: Execute the runner with a standard task.
2. **Assert Report Content**: Verify the metrics are realistic.
3. **Check Path Accuracy**: Ensure the "Branch B" is chosen for architectural tasks.

## Verification
- **Test Target**: `python3 tests/sandbox/runner.py --scenario docstring`
- **Expected Artifacts**: `artifacts/sandbox_stats.md`, `sandbox_events.json` (temp).
- **Linter Check**: `pytest tests/sandbox/runner.py` (if unit tests are added).
