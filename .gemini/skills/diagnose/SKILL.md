---
name: diagnose
description: Disciplined diagnosis loop for hard bugs and performance regressions, adapted for the Hub-and-Spoke architecture. Reproduce → minimise → hypothesise → instrument → handoff to planner → fix → regression-test. Use when the user reports a bug, exception, stack trace, or performance regression.
---
<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>


# Diagnose (Hub-and-Spoke Edition)

A discipline for hard bugs. In a Hub-and-Spoke model, debugging is not a monolithic activity; it is divided across specialized agents to protect context windows.

When exploring the codebase, use the `codegraph` MCP server and project domain glossary to get a clear mental model of the relevant modules. Call the MCP tool (codegraph_*) to gather precise context instead of reading full files, unless absolutely necessary (e.g., using grep_search for UI strings). 

## Checklist
- Run the extraction hook: `python .gemini/scripts/extract_stacktrace.py <logfile>` to isolate the error.

## Phase 0 — The Orchestrator's Checkpoint
**Actor: `@orchestrator`**

If a bug is reported, the Orchestrator MUST NOT delegate to the `@planner` immediately.
1. The Orchestrator MUST route the task to the `@planner` sub-agent.
2. The Orchestrator MUST instruct the `@planner` to activate the `diagnose` skill and produce a `artifacts/diagnosis_report.md`.

---

## Phase 1 — Build a feedback loop
**Actor: `@planner`**

**This is the most critical phase.** If you have a fast, deterministic, agent-runnable pass/fail signal for the bug, you will find the cause. If you don't have one, no amount of staring at code will save you.

1. **Failing test** at whatever seam reaches the bug — unit, integration, e2e.
2. **Curl / HTTP script** against a running dev server.
3. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
4. **Throwaway harness.** Spin up a minimal subset of the system.

**If you genuinely cannot build a loop in this environment:** Stop. State what you tried in your artifact. Do not proceed to Phase 2 until you have a loop you believe in, or you have explicit permission to proceed via static analysis alone.

---

## Phase 2 — Reproduce
**Actor: `@planner`**

Run the loop. Watch the bug appear.
Confirm the failure is reproducible across multiple runs and captures the exact symptom.

---

## Phase 3 — Hypothesise
**Actor: `@planner`**

Generate **3–5 ranked hypotheses** before testing any of them. Single-hypothesis generation anchors on the first plausible idea. Each hypothesis must be **falsifiable**: "If <X> is the cause, then <changing Y> will make the bug disappear."

---

## Phase 4 — Instrument & Conclude
**Actor: `@planner`**

Each probe must map to a specific prediction from Phase 3. Change one variable at a time using targeted logs or debugger inspection. Tag debug logs (e.g., `[DEBUG-a4f2]`).

Once the root cause is isolated, **DO NOT FIX IT**. You must write your findings to `artifacts/diagnosis_report.md`. The report MUST include:
1. The reproduction command/loop used.
2. The proven root cause.
3. Recommended seams for a regression test.
4. (Optional) Cleanup instructions for your debug logs.

---

## Phase 5 — The Fix Plan
**Actor: `@planner`**

The `@planner` consumes `artifacts/diagnosis_report.md`.
It creates a design doc and execution plan for the fix, focusing heavily on how to safely implement the fix without breaking adjacent features.

---

## Phase 6 — Fix + Regression Test
**Actor: `@implementer`**

The `@implementer` consumes the plan.
1. Write the regression test **before the fix** at the seam recommended by the Architect.
2. Watch it fail.
3. Apply the fix.
4. Watch it pass.
5. Re-run the Phase 1 feedback loop.
6. Clean up all `[DEBUG-...]` instrumentation left by the Architect.

---

**Then ask: what would have prevented this bug?** If the answer involves architectural change, hand off to the `improve-codebase-architecture` skill with specifics after the fix is merged.