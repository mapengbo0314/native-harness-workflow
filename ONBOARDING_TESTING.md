# Onboarding: The Harness Test Factory

Welcome! This guide explains how to extend the testing suite for the Agentic Harness. To maintain high quality, every new feature or LLM strategy should be verified across three layers: **Logic**, **Behavior**, and **Quality**.

## 1. Logic Layer (Deterministic)
**Location**: `tests/unit/`
**Tool**: `pytest`

Use this for code that has a single correct answer. 
- *Example*: An exclusion list for CodeGraph, path normalization, or CLI flag parsing.
- **How to add**: Create a new `test_<feature>.py` and use standard `pytest` patterns.

## 2. Behavior Layer (Sandbox Scenarios)
**Location**: `tests/sandbox/scenarios/`
**Tool**: `mise run sandbox:<scenario>`

Use this for end-to-end simulation of an agent turn.
- *Example*: Verifying that an agent can correctly add a docstring or fix a bug in a virtual environment.
- **How to add**: 
    1. Create a `tests/sandbox/scenarios/<name>.yaml` file.
    2. Define the `initial_prompt`, `expected_branch`, and any `files` to setup.
    3. The `SandboxRunner` will automatically detect and run it.

## 3. Quality Layer (LLM-as-a-Judge)
**Location**: `tests/benchmarks/`
**Tool**: `mise run benchmark`

Use this for non-deterministic behavior where "correctness" is a spectrum.
- *Example*: "Did the Orchestrator route the user correctly?" or "Is the generated system prompt relevant to the tech stack?"
- **How to add**: 
    1. Update the relevant test in `tests/benchmarks/`.
    2. Add a new `TestCase` with the input and the actual output.
    3. Use an LLM as a judge to score the response.

---

## High-Fidelity Benchmarking
We use **Gemini 2.0 Flash** for all live simulations to ensure high reasoning capability. 

### Running the Factory Audit
To run EVERYTHING in sequence and see the tradeoff reports:
```bash
mise run audit:harness
```
This command sequences unit tests, snapshots, security hooks, and the sandbox dry-run.
