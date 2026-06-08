---
Status: Proposed
Created: 2026-06-07
Supersedes: 2026-06-06-domain-model-system-design.md (DDD domain model — abandoned)
---

# Domain-as-Project-Ops Manifest

A small, authored `domain.json` that gives the agent the two kinds of knowledge it
can't get from source — **how to operate this repo** (operational) and **where the
product is going** (business) — delivered context-efficiently: deep facts *pulled*
on demand, a tiny business digest *pushed* only when judgment matters.

This supersedes the DDD domain model (invariants/glossary/bounded-contexts/per-turn
slice/edit-gate/reconciler), which was over-built and largely unwired.

---

## Section 0 — Problem

The harness mints an AI agent workflow into a target repo. To make good decisions
there, the agent needs knowledge it **cannot reliably derive from code**:

1. **Operational know-how** — how *this* repo is run, tested, deployed (commands,
   environments, infra). Lives in engineers' heads / scattered scripts.
2. **Product / business direction** — purpose, priorities, constraints, non-goals.
   Shapes *judgment calls*. Lives in PRDs / people's heads.

Today the agent guesses, re-asks, or gets it wrong. We want **one small source of
truth** the agent can **pull on demand** for operational depth and that **pushes a
tiny business digest into context** exactly on planning/question turns.

**Hard constraints (agreed):**
- No inferring meaning from code *structure* (unreliable — the deprecated
  "discovery" path). Code facts come only from reliable detectors and are
  human-confirmable.
- LLM used narrowly + safely: only to *summarize human-authored docs* into the
  business digest, never to invent facts. **No API key** — reuse the developer's
  already-authenticated local `claude`/`gemini` CLI.
- Minimal but streamlined manual burden: humans author only what only they know
  (deploy/env/infra commands, the source docs, curated references) via scaffolded
  slots.

## Section 1 — Technical Plan

**One store, two writers, two readers, reliable detectors, one safe LLM seam.**

**Store**
- `domain.json` at **`<plugin-root>/domain/domain.json`** (`.claude/harness-wf-plugin/domain/domain.json`) — *not* repo root. Operational half (`stack`, `environments`, `test`, `deploy`, `infra`, `references`) + business half (`business`: `direction`, `priorities`, `constraints`, `non_goals`).
- **User-owned + update-protected:** it lives inside the managed plugin, so `domain/**` is classified user-owned — `harness-wf update` (and re-mint) must never clobber it.
- Source docs: **`.claude/docs/reference/`** — human-authored product/business docs (compile input), kept with the other harness docs.

**Writers**
1. `domain-init` (tool-plane CLI, folded into `harness-wf init`): run detectors → fill `stack`; **scaffold** the manual sections as labeled empty slots with examples; create `.claude/docs/reference/` with a README.
2. `domain-compile` (tool-plane CLI): read `.claude/docs/reference/` → one isolated LLM call → small `business` digest → write back.

**Detectors (reliable, not code-inference)**
- **GitHub Linguist** via the GitHub `/languages` API (Linguist-powered) when an `origin` GitHub remote exists; graceful file-extension fallback offline → languages for `stack`.
- **cdxgen** (`npx`, same pattern as codegraph) → frameworks/ecosystems + services from k8s/docker-compose (can seed `infra`).

**LLM seam**
- `llm_client.query_llm` → shells to the developer's local `claude`/`gemini` CLI. **No API key, no new dependency** (existing harness code). Isolated one-shot call → the big doc-read never touches the working session.

**Readers**
1. `domain_ops(topic)` — domain MCP server, *pull on demand* for deep/operational facts (same always-reachable pattern as codegraph).
2. `build_context` — the existing per-turn `=== SYSTEM STATE ===` injector, extended to *push the tiny `business` digest* on **B (planning)** and **C (question)** branches only.

**Ecosystem fit:** bolts onto existing seams — `llm_client`, the MCP-server pattern, the `npx` tool pattern, the `build_context` injector, and `runtime_slice` (deploys `model.py`+`server.py` into minted plugins). Nothing architecturally new.

## Section 2 — Alternatives Ruled Out

1. **Full DDD domain model** (invariants/glossary/contexts/slice/gate/reconciler) — over-built, centerpiece unwired. → Superseded.
2. **Per-turn injection of a large slice** — context bloat + attention decay. → Pull + only the tiny business digest on B/C.
3. **Baked LLM digest for operational `references`** — staleness. → Pointers + read-on-demand. (`business` *is* a deliberately-accepted small, re-runnable baked digest.)
4. **Obsidian / wiki as the store** — heavy app dependency, no native LLM query, worsens context. → Markdown format usable for free in docs; `codegraph` for code.
5. **Main in-session agent reads all docs to compile** — pollutes working context. → Isolated one-shot call.
6. **Marker-file stack detection** ("pyproject exists → python") — lazy/inaccurate. → Linguist + cdxgen.
7. **API key for compile** — bad practice. → Local CLI auth, zero keys.
8. **Auto-detected `test` field** — confusing, low value. → Manual slot only.
9. **LLM inferring business/domain from code** (old discovery) — unreliable. → Summarize human docs only.
10. **`domain.json` at repo root** — clutter. → Inside the plugin.

## Section 3 — Detailed Implementation (every file)

Legend: NEW / MOD / KEEP. `<plugin>` = `.claude/harness-wf-plugin`. (This branch is fresh
off `main`, so the domain package is built from scratch; "reuse" means re-landing code
authored in the abandoned branch, adjusted.)

### A. Detectors
- **NEW `src/harness/domain/detect.py`** — `detect_languages()` (GitHub `/languages` API + extension fallback), `detect_frameworks()` (`npx @cyclonedx/cdxgen` parse → frameworks + services), `detect_stack()` combiner.
- **NEW `tests/unit/test_domain_detect.py`** — mock GitHub API + cdxgen subprocess; language weighting, framework/service extraction, offline fallback, cdxgen-failure degradation.

### B. Domain package
- **NEW `src/harness/domain/model.py`** — `OpsManifest` (7 topics incl. `business`); `topic()`; blank-dropping (list-aware). `test` is a section but never auto-detected.
- **NEW `src/harness/domain/server.py`** — `domain_ops(topic)` MCP tool; `find_manifest_path` resolves `DOMAIN_JSON_PATH` → `<plugin>/domain/domain.json`.
- **NEW `src/harness/domain/seed.py`** — `domain-init`: `detect.detect_stack()`; scaffold `environments`/`test`/`deploy`/`infra` as labeled slots; `references` manual-curated (detection only suggests); write `<plugin>/domain/domain.json`; scaffold `.claude/docs/reference/`.
- **NEW `src/harness/domain/compiler.py`** — `domain-compile`: read `.claude/docs/reference/`; bound input (per-doc cap + map-reduce when oversized); optional draft-approval; write `<plugin>/domain/domain.json`; local-CLI LLM seam. (Named `compiler.py`, not `compile.py`, to avoid shadowing the builtin.)
- **NEW tests:** `test_domain_model.py`, `test_domain_server.py`, `test_domain_seed.py`, `test_domain_compiler.py`.

### C. Runtime + hooks
- **MOD `src/harness/runtime/context_builder.py`** — `build_context()` renders a compact `business` digest into SYSTEM STATE **only on B and C**, with a render cap (truncate) so a verbose section can't bloat the turn.
- **MOD `src/harness/runtime/dispatcher.py`** — load `domain.json` (plugin-root resolution) and pass `business` into `build_context`; resilient to missing file.
- **NEW `tests/unit/test_context_builder_business.py`** — present on B/C, absent on A/D/E, omitted when empty, capped when large.

### D. CLI
- **MOD `src/harness/init/cli.py`** — `domain-init` / `domain-compile` subcommands + new paths + reference scaffold; `init` flow calls seed + scaffold.
- **NEW/MOD `tests/unit/test_cli_domain.py`** — routing + scaffold.

### E. Update-safety + registration + deployment
- **MOD `src/harness/update/classification.py`** — classify `<plugin>/domain/**` user-owned/excluded.
- **NEW `tests/unit/test_classification_domain_ownership.py`** — lock `domain/domain.json` never-touched by update (and re-mint preserves it).
- **MOD `src/harness/adapters/claude.py`** + **`.mcp.json`** — register `domain` MCP with `DOMAIN_JSON_PATH=<plugin>/domain/domain.json`.
- **MOD `src/harness/init/runtime_slice.py`** — add `model.py` + `server.py` to `RUNTIME_FILE_MAP` (deploy to plugin); detect/seed/compiler stay tool-plane.
- **MOD `src/harness/init/minting_engine.py`** + repo `CLAUDE.md` — add the `domain_ops` pointer (incl. `business` for judgment calls).

### F. Docs + dogfood
- **NEW `docs/domain/domain.schema.md`** — new schema, location, detect, compile, business.
- **NEW `.claude/docs/reference/`** (this repo) — author product/ops docs; run compile → populate the plugin `domain.json` (dogfood).
- This design + progress doc.

## Section 4 — Build Progression

Fresh branch `feat/domain-ops-manifest` off `main` (done). Phases, strict TDD,
one clean commit per phase:

- **Phase 0 — Docs.** This design + progress checklist. ← *current*
- **Phase 1 — Model + MCP.** `model.py` (OpsManifest) + `server.py` (domain_ops, plugin-path resolution).
- **Phase 2 — Detectors.** `detect.py` (Linguist API + fallback; cdxgen).
- **Phase 3 — Seed / init (scaffold).** `seed.py` detect+scaffold; CLI wiring; scaffold `.claude/docs/reference/`.
- **Phase 4 — Compile (author→business).** `compiler.py`: bounded read, draft-approval, plugin write.
- **Phase 5 — Consume (push).** `context_builder` business digest on B/C + `dispatcher` wiring.
- **Phase 6 — Update-safety + registration + deploy.** classification, `.mcp.json`/adapters `DOMAIN_JSON_PATH`, `runtime_slice` model+server.
- **Phase 7 — Dogfood + close.** Author `.claude/docs/reference/`, compile, populate plugin `domain.json`; `domain.schema.md`; full suite green.

The flow it realizes: **detect → scaffold → author → compile → consume.**

## Section 5 — Self-Review (red-team) + Mitigations

1. **Compile needs a local LLM CLI present + authenticated.** No CLI → compile fails. *Mitigation:* preflight `shutil.which` + clear message; `business` stays empty (graceful, not fatal).
2. **Business digest staleness.** Compiled = point-in-time; docs change → stale until re-run. *Accepted tradeoff* (manual re-run chosen). Optional staleness nudge deferred.
3. **Linguist API needs network + GitHub remote.** Offline / non-GitHub → extension fallback (less rich). *Mitigation:* solid fallback; `stack` is human-confirmable.
4. **cdxgen via npx is heavy / may fail.** First run downloads; restricted envs may block. *Mitigation:* best-effort with timeout; on failure, frameworks empty, languages still detected; never block init.
5. **Re-mint vs update.** Update protection isn't enough — `harness-wf init` over an existing workspace (smart-merge/backup) must also preserve `<plugin>/domain/domain.json`. *Mitigation:* verify re-mint path treats `domain/**` as user-owned; regression test both.
6. **Per-turn business cost on B/C.** A verbose `business` section would bloat every B/C turn. *Mitigation:* `build_context` render cap independent of stored size.
7. **Reference docs overflow the compile prompt** even with per-doc cap. *Mitigation:* map-reduce (per-doc summarize → merge) + bound doc count.
8. **`compile.py` shadows the builtin.** *Mitigation:* module named `compiler.py`.
9. **Sensitive docs go through the LLM.** They pass through the user's own `claude` CLI — same trust boundary as using Claude Code; no external API beyond existing auth. Acceptable; documented.
