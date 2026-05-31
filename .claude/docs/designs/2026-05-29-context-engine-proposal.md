---
title: Context Engine — Approaches & Tradeoffs Proposal
status: Proposed
date: 2026-05-29
author: harness brainstorming (Claude + Pengbo)
topic: context-engine
type: proposal
related:
  - src/harness/runtime/context_builder.py
  - src/harness/templates/boilerplate/hooks/prompt_classifier.py
  - src/harness/runtime/platform_adapter.py
---

# Context Engine — Approaches & Tradeoffs

## 0. Purpose

This is an **exploration / proposal** document (not an approved implementation plan).
It enumerates the realistic ways to build a "context engine" for the harness, the
tradeoffs of each, and a recommendation. The goal of the context engine:

> Keep a curated, high-signal body of project context **active and useful for the
> entire session**, fed into the model such that it survives compaction, resists
> "lost-in-the-middle" attention decay, and stays cheap (cache-friendly).

Two sub-requirements the user called out:

1. **Persistence** — the context engine must be active at all times in the session,
   not injected once and forgotten.
2. **Template / data form** — what data, in what shape, gives the model the most
   leverage per token.

## 1. The core mechanical constraint (why this is not trivial)

You cannot pin something into context "permanently" by writing it once. Two facts
drive every design below:

- **Attention is front- and back-weighted.** Transformers attend most strongly to
  the system-prompt prefix and to the most-recent tokens. Content in the middle of a
  long transcript is attended to weakly ("lost in the middle").
- **Compaction evicts the middle.** When the session grows, the harness summarizes
  older turns. Anything that lived only in a mid-conversation message can be
  summarized away or lost.

Therefore "active the entire session" decomposes into **two distinct injection
points** with different lifetimes:

| Lifetime                | Where it lives       | Mechanism                                   | Cache behavior           |
| ----------------------- | -------------------- | ------------------------------------------- | ------------------------ |
| Durable / slow-changing | System-prompt prefix | `SessionStart` hook `systemPromptExtension` | Cacheable IF byte-stable |
| Volatile / per-turn     | Most-recent position | `UserPromptSubmit` hook re-injection        | Re-sent every turn       |

The current implementation (`context_builder.build_context` invoked from
`prompt_classifier.py`) is a thin **volatile-only** layer. There is no durable tier.

## 2. Candidate approaches

### Approach A — Static bake-in (hand-maintained CLAUDE.md / AGENTS.md)

Put all context as prose in `CLAUDE.md` / `.claude/AGENTS.md`.

- **Pros:** Zero new machinery. Always in the prefix, always cached. Cross-platform
  (each CLI already loads its own root file).
- **Cons:** Hand-maintained → **drifts** the moment code changes. Prose form is
  low-density for the model. No volatile/state awareness (can't reflect current
  branch/phase/active design). Grows unbounded.
- **Verdict:** Necessary for the _constitution_ (mandates), insufficient as the
  engine. This is the baseline we already have.

### Approach B — Dynamic-only, enriched per-turn injection

Keep the existing `UserPromptSubmit` path; make `build_context` richer (branch,
phase, active docs, blockers, code-map snippets) and inject every turn.

- **Pros:** Already wired. Always near the most-recent position → high attention,
  survives compaction (re-stated each turn). Naturally reflects live state.
- **Cons:** **No prompt-cache benefit** — re-sent every turn, so a large block is
  paid for on every message. Forces a hard token budget (≈300 tokens) → cannot
  carry the full code map / glossary. Volatile-only means slow-changing reference
  data is paid for repeatedly with no caching.
- **Verdict:** Correct home for _state_, wrong home for _reference data_.

### Approach C — Two-tier (static cached prefix + dynamic state anchor) ★

Split the engine:

- **Tier 1 (static, cached):** constitution + routing matrix + agent/skill registry +
  CodeGraph-generated code map + glossary. Injected once via `SessionStart`,
  **byte-stable** so it earns prompt-cache hits.
- **Tier 2 (dynamic, per-turn):** compact state anchor — branch, phase, authority,
  active design/progress docs + `Status:`, open blockers, the current dispatch
  directive. ≤~300 tokens.

- **Pros:** Reference data is large but **paid once** (cache hits thereafter). State
  is small, fresh, and re-stated every turn (beats lost-in-the-middle + compaction).
  Maps 1:1 onto hooks we already own. Each tier has a single clear responsibility.
- **Cons:** Two render paths to maintain. Requires discipline: Tier 1 must stay
  byte-identical across turns (no timestamps/dict churn) or it busts the cache.
- **Verdict:** **Recommended.** Best cost/benefit; minimal new surface area;
  builds directly on existing hooks.

### Approach D — Retrieval-augmented (RAG) context

Embed the codebase/docs; at each turn retrieve the top-k relevant chunks and inject.

- **Pros:** Scales to huge repos; only surfaces what's relevant to the current
  prompt. Naturally fresh if re-indexed.
- **Cons:** Non-deterministic retrieval (same prompt → different chunks as the index
  changes) — at odds with the determinism goal. Heavy infra (vector store, embedder,
  re-index pipeline). Retrieved raw code is low-density vs a curated map.
  **CodeGraph already gives us structured retrieval on demand** — RAG would duplicate
  it less precisely.
- **Verdict:** Overkill now. The _pointers-not-payloads_ principle + on-demand
  CodeGraph queries achieve the benefit without the infra or the nondeterminism.

### Approach E — External memory / MCP context server

A stateful service (or MCP server) holds context and serves it via a tool the model
calls when it wants context.

- **Pros:** Centralized, queryable, can persist across sessions; clean separation.
- **Cons:** Pull-based → the model must _choose_ to call it; defeats "active at all
  times." Adds a network/process dependency. Most of its value is already covered by
  CodeGraph (structure) + the two-tier push (always-on).
- **Verdict:** Possible future add for _cross-session_ memory; not the core engine.

## 3. The "best data form" (orthogonal to the approach)

Independent of A–E, these principles maximize leverage per token and should be
baked into whatever we build:

1. **Declarative tables > prose.** The routing matrix as a table also makes the model
   self-route — reinforcing routing determinism.
2. **Pointers, not payloads.** Give a map + how to fetch (`codegraph_context <sym>`),
   not file contents. ~50 tokens instead of ~5,000, and stays current.
3. **Generated from a source of truth.** Code map ← CodeGraph; task state ← YAML
   `Status:` frontmatter of design/progress docs; recent changes ← git. Hand-kept
   data rots.
4. **Freshness markers.** Stamp Tier 1 with the commit SHA so staleness is visible.
5. **Negative space is signal.** "Out of scope / do NOT" is high-value
   (e.g. existing "No UI prototyping" mandate).

### Proposed template (rendered example)

**Tier 1 — `CONTEXT_ENGINE.md` (SessionStart, cached, byte-stable):**

```
=== HARNESS CONTEXT (commit <sha>) ===
§1 MANDATES: Graph-first. No prod code without approved plan. No UI prototyping.
§2 ROUTING MATRIX  (signal → branch → agent → skill → authority)        [table]
§3 AGENT REGISTRY  (name | purpose | tool boundary)                     [table]
§4 CODE MAP        (module | responsibility | entry symbol | query)     [generated, CodeGraph]
§5 GLOSSARY        (term | definition | canonical symbol)               [table]
```

**Tier 2 — state anchor (UserPromptSubmit, every turn, ≤300 tok):**

```
=== SESSION STATE (turn N) ===
Branch: D | Phase: In Progress | Authority: WRITE+TDD
Active design: <name>.md (Completed) → progress: <name>-progress.md (In Progress)
Open blockers: none
NOW: Skill("...") → <agent>. <one-line directive>.
```

## 4. Recommendation

- **Adopt Approach C (two-tier).** It is the only option that satisfies _both_
  "active all session" _and_ "cheap" — large reference data cached once, small live
  state restated every turn.
- **Layer the data-form principles (§3) on top**, with Tier 1 §2–§5 **generated**
  (CodeGraph + TOML routing table + doc frontmatter) so nothing is hand-maintained.
- **Defer D (RAG) and E (MCP memory)** until repo scale or cross-session memory
  demands them; CodeGraph + two-tier push covers current needs.

There is an obvious best choice (C). The non-obvious decisions that still need a
human call:

1. **Tier-1 injection home:** `SessionStart` hook vs a generated file included from
   `CLAUDE.md`. (Hook keeps it generated + out of source control churn; file is
   simpler but hand-include.)
2. **Code-map (§4) granularity:** module-level (cheap, ~30 lines) vs function-level
   (richer, needs token budgeting).
3. **Enforcement coupling:** does Tier 2's "NOW" directive stay advisory, or is it
   paired with a `PreToolUse` gate (ties into the routing-determinism refactor)?

## 5. Open questions / next step

This doc stays `Status: Proposed`. If C is accepted, the implementation should go
through the harness 5-part planning process (TDD) as its own design doc, since it
touches hooks, the minting/generation engine, and the platform adapters.
