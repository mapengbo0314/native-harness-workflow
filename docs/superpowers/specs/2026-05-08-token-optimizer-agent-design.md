# Token Optimizer Agent Design

## 1. Overview
The `token-optimizer` is a specialized subagent designed to autonomously measure, identify, and propose fixes for token inefficiencies within the Agentic Harness. It operates primarily by driving an enhanced Python test suite to holistically evaluate the context usage of the `boilerplate-agent` and other orchestrator setups.

## 2. Architecture & Components

### 2.1 The Agent Persona (`token-optimizer.md`)
- **Location:** `_agents/agents/token-optimizer.md` (and integrated into the relevant `agents.json` configurations).
- **Role:** Analytical auditor for context efficiency.
- **Workflow:** 
  1. Executes the test suite against target directories.
  2. Analyzes the resulting metrics for static overlap and dynamic context bloat.
  3. Presents an interactive proposal in the CLI chat detailing findings and specific refactoring plans.
  4. Applies optimizations (e.g., deduplicating markdown files, adjusting orchestrator summary logic) only after user approval.

### 2.2 The Test Engine (`tests/benchmarks/efficiency_suite.py`)
The existing `benchmark_efficiency_test.py` will be refactored and expanded into a modular test suite that the agent can invoke with specific flags.

#### Capabilities:
- **`--test-static`:** 
  - Analyzes markdown files (`GEMINI.md`, `AGENTS.md`, and specific agent prompts like `architect.md`).
  - Identifies high string/semantic overlap to highlight deduplication targets (e.g., rules repeated in both global mandates and local agent files).
- **`--test-goldfish`:** 
  - Mechanically simulates the Phase 3 Goldfish Protocol.
  - Loads a designated design doc and its referenced files into a mock LLM context.
  - Measures the exact token payload required to achieve "comprehension" independent of historical session context.
- **`--test-dynamic`:** 
  - Simulates a multi-turn task sequence (Phase 4 Implementation).
  - Traces the context window size as a task flows from Orchestrator -> Subagent -> Orchestrator.
  - Specifically flags "context leaks" where raw tool outputs (e.g., large file reads) fail to be summarized and bloat the parent orchestrator's history.

## 3. Data Flow & Output
The `tests/benchmarks/efficiency_suite.py` script must output its findings in a structured format (JSON or predictable markdown tables) that the `token-optimizer` can reliably parse without hallucinations.

## 4. Safety & Interaction
- The agent operates strictly in a "Test -> Propose -> Wait for Approval -> Apply" loop.
- It will not autonomously modify `harness/` infrastructure; its domain is limited to optimizing prompt markdown and rule configurations (`_agents/` and `boilerplate-agent/`).
- Fixes proposed must ensure that the Goldfish Protocol (Phase 3) still passes; token reduction cannot come at the cost of necessary context.