---
title: Langfuse Dispatcher Prompt Logging
status: Proposed
date: 2026-05-31
author: harness brainstorming (Claude + Pengbo)
topic: langfuse-observability
related:
  - .claude/docs/designs/2026-05-30-deterministic-routing-design.md
  - .claude/docs/designs/2026-05-27-langfuse-refactor-design.md
  - .claude/docs/designs/2026-05-27-langfuse-model-capture-design.md
---

# Langfuse Dispatcher Prompt Logging

> The deterministic routing design (2026-05-30) notes: "Langfuse measurement is kept as
> telemetry on top, not as the mechanism." This design makes that telemetry concrete —
> specifying exactly what gets logged at the dispatch boundary so that what the model
> _actually received_ is observable in Langfuse, not just metadata about _why_ it was routed.

## Part 1: Problem Understanding

### The Harness Dispatch Workflow

Every user prompt passes through this sequence before the model sees it:

```
stdin (prompt_classifier.py)
  │
  ├─ 1. raw prompt extracted
  ├─ 2. init_langfuse_prompt_span(prompt)          ← logs raw input only
  │
  ├─ 3. dispatcher.dispatch_agent("orchestrator", {prompt, project_root})
  │       └─ classify_intent(prompt) → branch (A/B/C/D/E)
  │       └─ evaluate_artifacts(branch, project_root) → {target_agent, phase, auth_msg, ...}
  │       └─ update_current_trace(matrix_branch, target_agent, phase)  ← metadata only
  │       └─ returns routing_decision
  │
  ├─ 4. context_builder.build_context(phase, target_agent, auth_msg, branch, ...)
  │       └─ builds system_state  (=== SYSTEM STATE === block)
  │
  ├─ 5. adapter.format_hook_response(original_prompt, routing_decision, system_state, ...)
  │       └─ builds modified_prompt = original_prompt + HARNESS DISPATCH directive
  │       └─ builds systemPromptExtension = system_state
  │
  ├─ 6. print(json.dumps(output))                  ← model receives this
  └─ 7. ensure_flush()
```

After step 7, Langfuse has:
- `user_prompt` span **input**: the raw prompt text (set in step 2)
- `dispatch_agent` span **metadata**: `matrix_branch`, `target_agent`, `phase`
- `query_llm` generation span: the classification LLM call

What Langfuse **does not** have:
- The `modified_prompt` — what the model actually received as its user turn
- The `system_state` — the SYSTEM STATE / HARNESS DISPATCH context block injected as the system prompt extension
- The assembled payload as a structured input/output pair on the `user_prompt` span

This means you cannot replay or audit a dispatch from Langfuse alone. You can see the routing decision, but not the actual prompt composition the model acted on.

### Why This Matters

The deterministic routing design's core promise is: "deterministic classification + deterministic directive." The directive (step 5 above) is half of that promise and it is invisible in Langfuse today. Without logging `modified_prompt` and `system_state`, you cannot:

- Verify the HARNESS DISPATCH directive was correctly assembled for the branch
- Detect directive drift (e.g. a Branch B prompt getting a Branch D directive)
- Reproduce a trace — the input to the model is unknown
- Measure how often the injected directive is obeyed vs. ignored

### Scope

This design covers **three files** across the deployed plugin and the harness source:

| File | Change |
|------|--------|
| `prompt_classifier.py` | Log `modified_prompt` + `system_state` as span output after step 5 |
| `langfuse_instrumentation.py` | Add `complete_prompt_span(modified_prompt, system_state, routing_decision)` helper |
| `dispatcher.py` | Log `original_prompt` + `system_state` as structured `input` on `dispatch_agent` span |

**File hierarchy:** `src/harness/runtime/dispatcher.py` is the single source of truth.
The deployed plugin copy at `.claude/harness-wf-plugin/src/dispatcher.py` is produced by
`copy_runtime_modules` at mint time and must be manually synced after editing the source —
it will not auto-update until the next mint. (`src/harness/dispatcher.py` does not exist;
references to it in older design docs are incorrect.)

---

## Part 2: The Span Payload Design

### `user_prompt` span (top-level, in `prompt_classifier.py`)

Currently: `input = prompt_text` (raw string), no `output`.

After this design:

```
input:  { "prompt": "<original user text>" }
output: {
    "modified_prompt": "<original> + HARNESS DISPATCH directive",
    "system_prompt_extension": "<SYSTEM STATE block>",
    "branch": "B",
    "phase": "Planning",
    "target_agent": "@implementer",
}
```

This makes the span a complete record of the dispatch boundary: what came in vs. what the model received.

### `dispatch_agent` span (in `dispatcher.py`)

Currently: metadata only (`matrix_branch`, `target_agent`, `phase`). No `input` or `output` at the Langfuse observation level.

After this design:

```
input:  { "prompt": "<original user text>", "agent": "orchestrator" }
output: {
    "intent_branch": "B",
    "target_agent": "@implementer",
    "phase": "Planning",
    "routed": true
}
```

The `system_state` belongs on the `user_prompt` span output, not the `dispatch_agent` span, because it is assembled in the hook after dispatch returns.

---

## Part 3: Implementation Plan

TDD throughout. Each new instrumentation path gets a test before the implementation.

### L-T1: Add `complete_prompt_span` to `langfuse_instrumentation.py`

**Rationale:** The hook currently has no way to log the assembled output back onto the
`user_prompt` span. A dedicated helper keeps the instrumentation call-sites thin and
consistent with the existing module pattern (`init_langfuse_trace`, `init_langfuse_prompt_span`,
`ensure_flush`).

`langfuse_instrumentation.py` already exists in the deployed plugin at
`.claude/harness-wf-plugin/src/langfuse_instrumentation.py` — adding a fourth function
requires no copy-path changes; the file is already present everywhere it needs to be.

```python
def complete_prompt_span(
    modified_prompt: str,
    system_state: str,
    routing_decision: dict,
) -> None:
    """Update the user_prompt span output with the assembled dispatch payload."""
```

- Test: mock `get_client`, assert `update_current_span` is called with the correct
  structured `output` dict (mirrors the pattern in existing tests for this module).
- Source of truth: `src/harness/runtime/langfuse_instrumentation.py`. The deployed
  plugin copy at `.claude/harness-wf-plugin/src/langfuse_instrumentation.py` must be
  manually synced after editing the source (same pattern as L-T3 / dispatcher).

### L-T2: Call `complete_prompt_span` in `prompt_classifier.py`

**Rationale:** This is the only place where both `modified_prompt` (from
`format_hook_response`) and `system_state` (from `context_builder`) are in scope at the
same time.

Call site — immediately after `output` is built from `format_hook_response`, before
`print(json.dumps(output))`:

```python
langfuse_instrumentation.complete_prompt_span(
    modified_prompt=output.get("modifiedPrompt", prompt),
    system_state=system_state,
    routing_decision=routing_decision,
)
```

- Test: end-to-end hook test — assert the Langfuse span output includes `modified_prompt`
  and `system_prompt_extension`.
- Applies to: template + deployed plugin.

### L-T3: Add structured `input`/`output` to `dispatch_agent` in `dispatcher.py`

**Rationale:** The `dispatch_agent` span currently captures metadata via
`update_current_trace` but has no structured `input`/`output` at the observation level.
This makes the span a first-class Langfuse generation record.

Add near the top of `dispatch_agent` (after `context` is validated):

```python
langfuse_context.update_current_observation(
    input={"prompt": context.get("prompt", ""), "agent": agent_name},
)
```

Add before `return` (after `routing_decision` is built):

```python
langfuse_context.update_current_observation(
    output={
        "intent_branch": intent_branch,
        "target_agent": routing_decision.get("target_agent"),
        "phase": routing_decision.get("phase"),
        "routed": True,
    }
)
```

- Test: mock `langfuse_context`, assert both `update_current_observation` calls fire with
  the correct keys.
- Applies to: `src/harness/runtime/dispatcher.py`, `src/harness/dispatcher.py`, and the
  deployed plugin copy.

### L-T4: Integration verification

After L-T1–L-T3 land, submit a test prompt and verify in Langfuse:

1. `user_prompt` span has structured `input` (raw prompt) and `output`
   (`modified_prompt`, `system_prompt_extension`, `branch`, `phase`, `target_agent`).
2. `dispatch_agent` span has structured `input` (prompt + agent) and `output` (branch +
   routing decision).
3. `modified_prompt` in Langfuse matches the `modifiedPrompt` value printed to stdout.
4. The HARNESS DISPATCH directive is visible verbatim inside `modified_prompt`.

---

## Part 4: Open Issues

- **O1 — Prompt truncation policy. RESOLVED.** Langfuse logging is a pure HTTP call —
  no token cost. Log full text always; Langfuse stores it fine and full fidelity is more
  useful than truncated.

- **O2 — Fallback path coverage. RESOLVED.** Both the happy path (`format_hook_response`)
  and the inline fallback `except` block set `output["modifiedPrompt"]`. Placing the
  `complete_prompt_span` call at line 204 (before `print(json.dumps(output))`) covers both
  paths with no special handling needed.

- **O3 — Copy mechanism dependency. RESOLVED.** `langfuse_instrumentation.py` already
  exists in the deployed plugin (`harness-wf-plugin/src/`). Adding `complete_prompt_span`
  to the existing module requires no copy-path changes.

---

## Part 5: Alternatives Considered

- **Log `modified_prompt` as a separate Langfuse generation (as_type="generation").**
  Rejected: the `user_prompt` span already represents the full hook invocation. Adding a
  synthetic generation record would duplicate the span hierarchy without adding signal.

- **Log in `format_hook_response` inside the adapter.** Rejected: adapters have no
  Langfuse dependency and should not gain one. The hook is the right instrumentation
  boundary.

- **Log only the HARNESS DISPATCH directive (delta), not the full `modified_prompt`.**
  Rejected: the full `modified_prompt` is what the model saw. Logging only the delta makes
  replay impossible without reconstructing the original prompt separately.
