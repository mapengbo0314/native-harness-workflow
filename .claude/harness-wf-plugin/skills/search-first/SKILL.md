---
name: search-first
description: Use before writing source code for planning-phase work - researches existing solutions (Adopt/Extend/Compose/Build) so designs build on prior art instead of assumed knowledge. Records research_done in the session store, which releases the search-first gate.
---

# Search-First Research Pass

Before designing or implementing from assumed knowledge, research what already exists. This skill performs that pass and records `research_done` in the session store — the deterministic search-first gate holds source writes during the planning phase until this skill (or its waiver) completes.

## Step 1 — Proportionality check (waiver hatch)

Not every task deserves a research pipeline. **First**, ask: is the approach already decided, or is this well-trodden ground (a pattern this codebase or team has shipped before, a standard library use, a mechanical change)?

If YES — record a one-line waiver and exit (~30 seconds, no research):

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/session_phase.py" set-research-done --note "waiver: <one line why research is unnecessary>"
```

Then stop. The gate is released; proceed with the work.

If NO — continue to Step 2.

## Step 2 — Enumerate unknowns

List the specific questions the design depends on (max 5). For each: what would change in the design if the answer differs from your assumption?

## Step 3 — Research

For each unknown, in priority order:

1. **This codebase first** — `codegraph` MCP (`codegraph_context`, `codegraph_search`): does something here already solve or partially solve it?
2. **Dependencies already installed** — does a library in the lockfile cover it?
3. **The ecosystem** — established libraries, frameworks, or patterns (WebSearch/WebFetch when available). Prefer maintained, widely-adopted options; note license and maintenance signals.

Cite what you find: file paths for internal findings, URLs/package names for external ones.

## Step 4 — Adopt / Extend / Compose / Build matrix

Force the findings through the decision matrix, in this order of preference:

| Outcome | Meaning | Choose when |
|---|---|---|
| **Adopt** | Use an existing solution as-is | An internal module or maintained library covers ≥90% of the need |
| **Extend** | Build on an existing solution | Something covers the core; the gap is additive and small |
| **Compose** | Combine existing pieces | Two or more existing parts cover it with thin glue |
| **Build** | Write it new | Nothing fits, or integration cost exceeds building |

State the matrix outcome and its one-paragraph justification. **Adopt beats Extend beats Compose beats Build** — building new code requires explaining why the higher options lost.

## Step 5 — Record the research

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/session_phase.py" set-research-done --note "<matrix outcome>: <one-line summary>"
```

Attach the findings (unknowns → answers → citations → matrix outcome) to the working context: into the design doc's research section when one exists, otherwise as a compact summary in your next message.

## Step 6 — Post-research depth checkpoint (HITL)

The research is done; now right-size the rest of the process. Ask the user via `AskUserQuestion`:

- **Quick implementation** — hand off to direct TDD execution with the research findings attached (Branch D semantics, no design doc). Clear the planning phase so the gate releases:

  ```bash
  python3 "$CLAUDE_PLUGIN_ROOT/scripts/session_phase.py" clear-phase --artifact "research: <matrix outcome>"
  ```

- **Full planning pipeline** — continue with `harness-brainstorming-plans` to a reviewed design doc; the findings feed Section 2 (Technical Plan) and Section 3 (Alternatives).

The matrix outcome sets the **recommended default**: Adopt/Extend ⇒ recommend quick implementation; Compose ⇒ judgment call based on glue complexity; Build ⇒ recommend full planning.