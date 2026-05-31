---
title: Deterministic Routing
status: Proposed
date: 2026-05-30
author: harness brainstorming (Claude + Pengbo)
topic: deterministic-routing
supersedes_partial: 2026-05-28-deterministic-skill-agent-routing-design.md
split_from: 2026-05-29-harness-fluidity-design.md
related:
  - .claude/docs/designs/2026-05-29-harness-fluidity-design.md
  - .claude/docs/designs/2026-05-29-context-engine-proposal.md
---

# Deterministic Routing

> Extracted from the Harness Fluidity design (2026-05-30). The fluidity work
> (single-source adapters + mint-verify safety net) is a **prerequisite**: this design
> ships routing logic into minted plugins via the _same copy mechanism_ that fluidity
> establishes for the runtime adapter, and verifies routing through the fluidity
> mint-and-verify matrix.

## Part 1: Problem Understanding

The 2026-05-28 work unified the routing _table_ and the dispatch _directive format_, but
left the actual decision stochastic. Concretely, in `src/harness/runtime/dispatcher.py`
and the minted hook:

1. **Three disagreeing classifiers.** (a) dispatcher LLM `classify_intent`
   (`dispatcher.py:149`, default branch `B` at `dispatcher.py:228`); (b) a dispatcher
   keyword fallback in the same file (`dispatcher.py:209-228`, default `B`); (c) the hook
   `fallback_classify` (`prompt_classifier.py:43`, default `E` at `:53`). Their keyword
   sets and defaults genuinely diverge.
2. **The LLM classifier has no temperature/seed**, so the same prompt can route
   differently turn to turn.
3. **`evaluate_artifacts` computes design/progress state but never uses it for the
   phase** — phase is a static `phase_map[branch]` (`dispatcher.py:301-307`).
4. **A live Branch B/D contradiction** (Defect 1): the routing/phase tables force TDD via
   `implementer` for D, while `assemble_branch_context`'s branch hint says "fast-path
   generalist" (`dispatcher.py:252`).
5. **Enforcement is advisory only** — the hook injects a directive; nothing blocks a
   write when the active phase is read-only.

**Goal:** make the routing _decision_ deterministic and reproducible, redefine Branch D
coherently, and add a negative enforcement gate — **without** changing the harness's
advisory execution model.

### Decisions locked with the user

- **Advisory injection is BY DESIGN — do not replace it.** The hook never spawns agents;
  it classifies → injects a `HARNESS DISPATCH` directive into `modifiedPrompt` → the model
  acts on it. The user explicitly rejected programmatic-orchestration substrates (an MCP
  orchestrator loop and an Agent-SDK runtime) because both break the interactive harness.
  Therefore **"deterministic routing" means deterministic _classification_ + deterministic
  _directive_ + a negative _PreToolUse gate_** — NOT code-forced tool invocation. The
  guarantee is asymmetric: we can deterministically _prevent_ the wrong action; we cannot
  _force_ the right one, and that is accepted.
- **Branch D = fast path** — trivial, localized edits, no forced TDD. B-execution and
  A-fixes keep TDD. Boundary: _introduces/alters behavior or logic → B; trivial &
  localized → D._ This resolves Defect 1, but only if **all five** D-bearing structures
  are reconciled (see R-T6).
- **One classifier, shipped into the plugin by copy.** The dispatcher and the minted hook
  call the same `classify`. Since the hook cannot `import harness.routing`, the classifier
  - routing table are copied flat into the plugin via the fluidity design's
    `copy_runtime_modules` path (same mechanism as the runtime adapter).
- **Deterministic-first classification**, optional temp-0 LLM tiebreak — the LLM is a
  fallback, not the spine.

## Part 2: Technical Plan

Extract a `src/harness/routing/` package: one routing table (data), one classifier
(deterministic-first; optional temp-0 LLM tiebreak), one phase resolver. The dispatcher
and the hook both call this one classifier — the three divergent classifiers collapse to
one. Branch D is redefined as the fast path (resolves Defect 1). A `PreToolUse` hard gate
denies write tools when the active phase is read-only (A/C), turning advisory routing into
enforced routing. The fluidity mint-and-verify matrix verifies all of it end-to-end.

**Prerequisite:** the fluidity design's copy mechanism (its S2-T6) must land first, so the
classifier can be shipped into the plugin the same way.

## Part 3: Alternatives Considered

- **Keep the LLM classifier as primary, just pin temperature.** Rejected as primary:
  still opaque and slower per turn. Deterministic-first rules with an optional temp-0
  tiebreak give reproducibility and speed; the LLM is a fallback, not the spine.
- **Stay advisory + measure drift in Langfuse (no gate).** Rejected: advisory-only was
  flagged as a defect. A `PreToolUse` gate is the only thing that makes "STRICTLY
  UNAUTHORIZED" true. (Langfuse measurement is kept as telemetry on top, not as the
  mechanism.) Note this is the _negative_ half of enforcement — consistent with the
  advisory-by-design decision; we block wrong writes, we do not force right calls.
- **Programmatic orchestration (MCP loop or Agent-SDK runtime that spawns agents in
  code).** Rejected by the user: it would make invocation deterministic but break the
  interactive hook-based harness. Recorded so it is not re-proposed.

## Part 4: Detailed Implementation Plan

TDD throughout: each behavior gets a failing test (RED) before minimal code (GREEN).
_Branch D's "fast path" is about routing behavior; we still build the routing package
tests-first._

**`src/harness/routing/routing_table.toml`** (new) — Rationale: one source of truth for
branch → behavior.

- R-T1: Per branch A–E: `description`, `signals` (anchored keyword/regex rules with
  priority), `skill`, `agent`, `agent_invokes_skill`, `authority`, `default_phase`.
  Branch D = fast path (agent: generalist/lightweight, skill: none, authority:
  write-surgical, no TDD); Branch B execution + A keep TDD authority.

**`src/harness/routing/classifier.py`** (new) — Rationale: ONE classifier replacing the
three.

- R-T2 (RED first): `classify(prompt) -> RoutingResult` — deterministic-first using the
  table's prioritized, mutually-exclusive signals; single defined default; optional temp-0
  LLM tiebreak behind a confidence threshold; returns branch + confidence + source.
  `tests/unit/test_classifier.py`.
- R-T2b (regression corpus): before unifying, capture a corpus of prompts and the branch
  each of the **three** current classifiers returns; assert the unified classifier's
  output is an intentional, reviewed mapping — not silent drift (closes the equivalence
  gap; the three keyword sets diverge today).

**`src/harness/routing/phase_resolver.py`** (new) — Rationale: make phase a function of
artifact state, not just branch.

- R-T3 (RED first): `resolve_phase(branch, project_root, designs_dir) -> Phase`. The
  designs directory is **parametrized** (the harness repo uses `.claude/docs/designs/`; a
  minted plugin uses its own `docs/designs/`). See Open Issue O2.
  `tests/unit/test_phase_resolver.py`.

**`src/harness/runtime/dispatcher.py`** (modify) — Rationale: consume the routing package;
kill dead/contradictory code.

- R-T4: Replace `classify_intent` (3 paths) with `routing.classifier.classify`.
- R-T5: Replace `BRANCH_ROUTING` + static `phase_map` with table + `phase_resolver`; use
  `project_root`.
- R-T6: Fix Defect 1 — reconcile **all five** D-bearing structures to the fast path:
  `BRANCHES["D"]` (`dispatcher.py:87`), `BRANCH_ROUTING["D"]` (agent `implementer` +
  `agent_invokes_skill:True`, `dispatcher.py:99`), `phase_map["D"]` (`dispatcher.py:305`),
  the routing table `D`, and `assemble_branch_context` branch hint (`dispatcher.py:252`).
  Fixing only three leaves TDD half-enforced.

**`src/harness/templates/boilerplate/hooks/prompt_classifier.py`** (modify) — Rationale:
remove the third classifier.

- R-T7: Delete `fallback_classify`; call the unified classifier. Ship `classifier.py` +
  the routing table into the plugin by the **same copy mechanism as the fluidity runtime
  slice** — copied flat, zero `harness.*`. This is what makes "collapse to one classifier"
  reachable inside the minted plugin, which cannot import `harness.routing`.

**`src/harness/templates/boilerplate/hooks/pre_tool_use.py`** (modify) — Rationale:
enforced (negative) binding.

- R-T8 (RED→GREEN): Deny write tools (Edit/Write/mutating Bash) when the active phase is
  read-only (A diagnosis / C question); allow in D/B-execution.
  `tests/hooks/test_pre_tool_use_gate.py` (new). **Depends on O1 + O3** — the phase must be
  persisted somewhere the gate can read it, and "mutating Bash" must be defined.

**`tests/integration/test_routing_determinism.py`** (new) — Rationale: prove the goal.

- R-T9: Same prompt classified N times → identical branch; the B/D boundary cases resolve
  as specified; read-only branches block writes; the unified classifier matches the
  reviewed R-T2b mapping.

- R-T10 (cross-cutting): Re-run the fluidity mint-and-verify matrix to confirm minted
  Claude+Gemini plugins route deterministically end-to-end.

## Part 5: Open Issues / Prerequisites (must resolve before R-T8)

These are load-bearing inputs the gate and phase resolver assume but that **do not exist
in the repo today**. They were surfaced in adversary review and are unresolved:

- **O1 — No persisted phase.** `campaign_state.json` is written by the hook
  (`prompt_classifier.py:127`) but stores only `active_persona` (`~:147-152`) — there is
  **no** `phase`/`read_only`/branch field. The phase is computed only transiently in
  `dispatcher.evaluate_artifacts` (`dispatcher.py:301-311`). **Decision needed:** make the
  classifier write the resolved phase into `campaign_state.json` (add as an explicit task),
  and define fail-open vs fail-closed when the field is absent.
- **O2 — Phase-source path & vocabulary.** `resolve_phase` must glob the _right_ designs
  dir (`.claude/docs/designs/` in this repo, not root `docs/designs/` which is empty), and
  `Status:` frontmatter today is a **lifecycle** label (`Proposed`/`In Progress`), not a
  routing **phase** (Planning/Execution/Discovery). **Decision needed:** define the phase
  vocabulary and who writes it (the orchestrator at `.claude/AGENTS.md` /
  `.claude/orchestrator.md` is currently a stub).
- **O3 — "Mutating Bash" detection is undefined.** R-T8 lists "mutating Bash" without a
  detection rule, risking false-blocks on diagnostic shell and false-allows on
  side-effecting reads. **Decision needed:** an allowlist/denylist or a conservative
  default.

## Part 6: Adversary Notes (routing-relevant, ported from the fluidity design)

Method: claims were verified against source at review time (2026-05-29) and re-checked
2026-05-30. File:line evidence retained; stale "design line" references replaced with task
ids. Adapter/mint-only defects (former D1, D2) stay with the fluidity design.

**D3 — `campaign_state.json` has no phase field.** (Now tracked as O1.) The gate reading
"the active phase from `campaign_state.json`" finds a file that exists but lacks the field
it needs. Refinement C1: the file stores only `active_persona`; the design must also make
the classifier persist the resolved phase. Refinement C2: `pre_tool_use.py` today blocks
`rm`/`.env` (`pre_tool_use.py:79-86`) and reads only `tool_name`/`tool_input` (`:75-76`) —
it has no access to phase at fire time; the gate is a build, not a modify.

**D4 — Phase-source path.** (Now O2.) Root `docs/` exists and is git-tracked
(`docs/domain/CONTEXT.md`), but `docs/designs/` is empty; designs live under
`.claude/docs/designs/`. A resolver globbing `project_root/docs/designs` finds nothing in
the harness repo. R-T3 parametrizes the dir to fix this.

**D5 — `Status:` is lifecycle, not phase.** (Now O2.) Current docs emit `Proposed`; the
resolver needs a Planning/Execution vocabulary nothing writes yet.

**D6 — Classifier package-availability asymmetry.** The dispatcher runs with `harness`
importable; the minted hook does not. "Collapse to one" is only reachable if the classifier

- table are shipped standalone into the plugin. **Addressed by R-T7** (copy mechanism from
  the fluidity design) — this was the same standalone problem fluidity solves for adapters.

**D7 — Keyword sets diverge today.** Dispatcher D keywords `["typo","change color","minor
update","fix the"]` (`dispatcher.py:224`) vs hook D keywords
`["rename","typo","comment","format","small change","tweak","edit"]`; `"fix"` lands in
different branches; defaults differ (dispatcher B, hook E). Unifying silently reclassifies
some prompts. **Addressed by R-T2b** (regression corpus + reviewed mapping); R-T9 asserts
the mapping, not just self-consistency.

**D8 — Branch D reconciliation is incomplete.** Five structures describe D and disagree;
the original fix listed only three. **Addressed by R-T6** (reconcile all five). Until then,
"Defect 1 resolved" is not true.

**D9 — Import-rewrite is narrower than routing needs.** `copy_runtime_modules` rewrites
only `harness.(runtime|init).*` (`minting_engine.py:620-621`). A copied classifier must be
zero-`harness.*` or the regex set must be widened. **Tracked in R-T7** (shared with the
fluidity copy step).

**Undocumented assumptions (routing):**

- A1 → O1. `campaign_state.json` carries a read-only-phase flag at fire time. It does not.
- A2/A3 → O2. `docs/designs/*.md` resolves in the harness repo (it does not); `Status:`
  encodes a routing phase (it encodes lifecycle).
- A4. An orchestrator state machine writes phase state — `.claude/AGENTS.md` /
  `.claude/orchestrator.md` are stubs.
- A5 → D6/R-T7. One classifier module can serve both contexts only with the copy path.
- A9. S3 depends on the fluidity copy mechanism to ship routing logic without `harness.*`;
  reverting the fluidity work undermines this design.
- A10 → O3. The gate must distinguish safe reads from writes; "mutating Bash" is undefined.

#### Overall Verdict (as specified, pre-Open-Issues)

High-risk until O1–O3 are resolved: the gate's two load-bearing inputs (a persisted phase
and a phase vocabulary) do not exist yet, and Defect 1 is only resolved if R-T6 reconciles
all five D structures. The classifier-unification feasibility (D6/D9) is resolved by
reusing the fluidity copy mechanism (R-T7).
