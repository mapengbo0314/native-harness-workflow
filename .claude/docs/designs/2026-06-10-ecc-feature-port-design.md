# ECC Feature Port — Five Capabilities on the domain.json Spine

*Status: APPROVED — Sections 0–3 HITL-approved; revised per Section 4 adversarial findings (C1–C4, M1–M6, m1–m4); amended per Section 5 second-round review (R1–R5)*
*Date: 2026-06-10 · Foundation: PR #36 (domain.json + domain_ops MCP)*

---

## Section 0 — Problem Understanding ✅ approved

The harness today is a *static* assistant. PR #36 gave it a spine — `domain.json` tells
the AI what the repo's stack, commands, and business priorities are — but everything
around that spine is one-shot and forgetful:

1. **Knowledge evaporates.** Patterns, decisions, and blocker resolutions discovered in
   a session die with the session. (→ F1 Continuous Learning, F5 Session Memory)
2. **Guidance is generic.** A Django repo and a Go microservice get identical rules.
   Stack-specific anti-patterns sail through review. (→ F3 Rules Packs)
3. **Plans are built on stale assumptions.** The planner designs against training-data
   knowledge instead of researching first, so designs get reworked late. (→ F4 Search-First)
4. **Risk is caught in a single pass, or not at all.** No exploit-chain depth, no
   auditable risk artifact for compliance. (→ F2 Adversary Pipeline)

**Who hurts:** enterprise teams sharing one repo harness across engineers and shifts —
they need consistency, continuity across hand-offs, and auditability.

**Approved scope:** one design doc, phased by dependency: **F3 → F5 → F1 → F4 → F2**.

---

## Section 1 — Technical Plan ✅ approved (revised per Section 4)

**Architecture constraint that shapes everything:** `harness-wf` *mints* a plugin into
target repos. Code in `src/harness/templates/boilerplate/` is copied into each project
at init; `src/harness/runtime/dispatcher.py` routes prompts to branches/agents;
`src/harness/init/` does detection + minting; `src/harness/update/` keeps deployed
copies upgradable via an ownership manifest + 3-way merge. So **every feature has two
halves**: tool-plane code that mints it, and the deployed-plane artifact that runs in
the target repo. Every new minted file must be registered with the update manifest or
`harness-wf update` will fight it.

> Note: the original 1-pager's file paths were partly fictional
> (`src/harness/orchestrator/`, `src/harness/state/`, root-level `hooks/` don't exist;
> `src/harness/domain/detect.py` IS real). This doc uses the real layout.

### Phase 1 — F3 Rules Packs (init-time + update-plane awareness)
Packs live in `src/harness/templates/boilerplate/rules/packs/` (`common/` + per-language).
At init (and domain refresh), the minting engine reads `domain.json → stack` and copies
only matching packs into the target's `.claude/rules/harness/` (namespaced subdir to
avoid colliding with user rules — ECC pattern). Revisions per Section 4:
- **Every language pack file carries `paths` frontmatter** (e.g. `paths: ["**/*.py"]`)
  so it is lazy-loaded only when matching files are touched — not flat-loaded into every
  session (M3, context table). `common/` files stay un-scoped but get a hard size budget.
- **Language alias map** (`Go`→`golang`, `TypeScript`→`typescript`...) because Linguist
  emits display names and `stack` also mixes in cdxgen framework names; matching is
  language-aware, not substring (m2).
- **The update plane must respect the stack filter** (C4): the stack selection is
  persisted in the manifest's `render_context`, and `enumerate_source_producers` /
  `compute_verdicts` skip pruned packs so `harness-wf update` doesn't re-deliver
  `golang/` to a Python repo forever.
- **Per-platform consumption matrix:** Claude auto-loads `.claude/rules/` (verified);
  gemini/codex/cursor/generic get packs inlined into agent personas via the existing
  `@../rules/` include mechanism at mint — no auto-load assumed (M3).
- **Ownership: the installed dir is a generated mirror (R1).** The C4 fix alone stops
  *re-delivery of pruned packs* but never answers who delivers *updates to installed
  packs* — `.claude/rules/harness/` sits outside the plugin dir, and the manifest walks
  `plugin_dir` only, so pack content shipped in harness v2 would never reach a v1 repo.
  Resolution: source of truth stays in `templates/boilerplate/rules/packs/` (in-manifest,
  normal producers); the deployed `.claude/rules/harness/` dir is recorded in the
  manifest's `render_context` as an **install target** and *regenerated* (re-prune +
  re-copy) on every `init` / `update` / `domain-refresh` — never 3-way merged, never
  operator-edited (user rules live beside the namespace, not inside it). Same model as
  `features.json`: generated, recompiled, ownership question dissolves.

### Phase 2 — F5 Session Memory (the state store)
**Corrected lifecycle semantics (C1):** `Stop` fires after *every response*, not at
session end. So the digest write happens on `Stop` but is **cheap and idempotent**
(overwrite of this session's own file); `SessionEnd` marks the session closed.
- **Per-session files** `state/session_memory_<session>.json` (same convention as
  `tdd_<session>.json`), merged into one digest at read time — no single shared file,
  no lost-update race between concurrent engineers (M6).
- A `SessionStart` hook reads the store and injects a digest with **hard caps (ECC
  numbers): ≤ 8 KB total, ≤ 6 entries injected, ≤ 220 chars per entry summary,
  30-day retention**, plus an opt-out env (`HARNESS_SESSION_CONTEXT=off`).
- A `PreCompact` save mirrors ECC's pattern so context survives compression.
- **Entry schema, versioned from day one (R4):** "merged into a digest" is
  unimplementable without a format. Each entry is
  `{schema_version, ts, session_id, kind: decision|blocker|pattern|phase,
  summary (≤220 chars), refs[]}`. Merge-at-read is **deterministic** — recency-first
  ordering, dedup on `(kind, normalized-summary)`, fixed tie-break on `(ts, session_id)`
  — so two reads of the same store produce byte-identical digests and the idempotent
  `Stop` write stays genuinely idempotent. `schema_version` lets Phase 3 and the phase
  keys evolve the format without migrations.
- **Sticky-phase keys ship here (R2):** `phase`, `phase_entered_at`,
  `phase_exit_artifact` are first-class store keys (the `kind: phase` entry), written
  by skills entering/exiting planning or TDD execution. Phase 4's gate is their first
  consumer; the deferred state machine (follow-up #1) is the second.
- **Platform support matrix (M4):** Claude — full support at launch. gemini —
  `Stop`/`SessionStart` need new `event_mappings` entries; ship only after verifying
  Gemini CLI equivalents exist. codex/cursor/generic — no hook runtime today; F5/F1
  are explicitly Claude-first, documented as such.

### Phase 3 — F1 Continuous Learning (write-back loop)
Extraction triggers on **`SessionEnd`** (not `Stop` — C1), handing the transcript to the
existing LLM client (`src/harness/runtime/llm_client.py`) to extract reusable patterns
as `SKILL.md` files tagged with stack/business context from `domain.json`. A `/learn`
skill triggers the same extraction on demand. Revisions per Section 4:
- **Recursion guard (C2):** the hook exits immediately when
  `HARNESS_INTERNAL_LLM_CALL=1` (the LLM client already sets it; we add the consumer),
  plus a lockfile so overlapping extractions can't stack.
- **Out-of-repo storage (C4 + ECC v2):** learned skills land in
  `~/.local/share/harness-wf/projects/<repo-hash>/learned/`, *outside* the plugin tree —
  invisible to the update manifest (can't brick `harness-wf update`) and immune to
  repo-to-repo contamination. `SessionStart` (Phase 2) injects **≤ 6** learned-skill
  summaries per session.
- **Quality guards (ECC v2):** minimum-session-length threshold (≥ 10 turns) before
  extraction runs; confidence + dedup metadata in each learned skill's frontmatter.
- **Fail-open** stands: any failure logs and exits 0; extraction never blocks anything.

### Phase 4 — F4 Search-First Gate (two-layer: steering + enforcement)
New Branch B pre-condition: before planning proceeds, a structured research pass must
be completed and recorded in session state (Phase 2's store). **Honest architecture
(M1, M5):** the dispatcher is advisory-only (its output is an `additionalContext`
directive the model may ignore) and stays **routing-only** — the gate lives in the
deployed plane instead:
1. **Steering layer:** `context_builder.py` (which assembles the SYSTEM STATE block)
   surfaces gate status on every Branch-B prompt.
2. **Enforcement layer:** `pre_tool_use.py` — the codebase's only deterministic block
   point (same mechanism as the TDD gate) — blocks the first source-file write until
   `research_done` is set, keyed to **persisted phase, not per-prompt branch
   classification (R2)**. The classifier observably flips branches mid-workflow
   (B → E → C during this very design session), so a gate keyed to the current
   classification fires spuriously on misrouted prompts and evaporates when a planning
   session flips out of B — a deterministic gate on a nondeterministic predicate is not
   enforcement. Instead: entering planning (the brainstorming skill's first act) sets
   `phase=planning` in the session store (Phase 2's R2 keys); the gate holds while
   `phase=planning` until `research_done` is set or the phase exits; no persisted
   phase ⇒ passthrough. The classifier's branch output stays advisory.
The `search-first` skill performs the research and sets the flag, and adopts ECC's
**Adopt / Extend / Compose / Build decision matrix** (the highest-value part of ECC's
version — it prevents writing code at all when adoption wins).

**Proportionality guards (post-review follow-up)** — the gate must not drag simple,
already-decided implementations through a research pipeline:
- **Bias-to-D intent classification:** the `classify_intent` prompt
  (`src/harness/runtime/dispatcher.py:149`) and the `prompt_classifier` fallback
  heuristics are updated: *when uncertain between Branch B (planning) and Branch D
  (direct implementation), choose D*. Branch B is for genuinely open design work;
  D's pre-flight handles missing context by asking the user 1–2 clarifying questions
  (`AskUserQuestion`), never by escalating into the research pipeline.
- **Waiver escape hatch:** step 1 of the `search-first` skill is a proportionality
  check — if the user already knows the approach or the ground is well-trodden,
  record a one-line research waiver, set `research_done`, and exit (~30 seconds,
  no web research).

### Phase 5 — F2 Adversary Pipeline (multi-agent, tiered + budgeted)
A stress-test skill against a design doc, writing a prioritized risk report to
`docs/adversary/`. **Tiered (post-review follow-up):** running the deep multi-agent
pipeline on every design is too slow/expensive (observed: ~24 min, ~194k tokens,
97 tool calls for one deep review).
- **Tier 1 (default, every design):** council-style single-context review — the
  current agent applies Attacker/Defender/Auditor role lenses *inline*, no subagents
  (ECC's `council` pattern: cheap, minutes, catches reasoning flaws).
- **Tier 2 (opt-in, multi-subsystem designs):** the three sequenced agent passes —
  **Attacker → Defender → Auditor** — each with a budget: max tool calls (default 30),
  max files read (default 12), model tier (Attacker/Defender on a smaller model;
  Auditor synthesis on the big one), and a "summarize what you have and stop when the
  budget hits" degrade-gracefully clause.
- **Budget enforcement is deterministic, not requested (R5):** a budget in a dispatch
  prompt is a directive the agent may ignore — the observed 194k-token run is exactly
  an agent not self-limiting. Before each Tier-2 dispatch the skill writes a **budget
  sidecar** `state/budget_<session>.json` (max tool calls, max file reads, counters);
  `pre_tool_use.py` increments the counters and **hard-blocks** past the limit with a
  "summarize what you have and finish" message (exit 2) — the same deterministic layer
  as the TDD and F4 gates. No sidecar ⇒ passthrough (zero cost to normal sessions);
  the prompt clause remains as graceful steering before the wall.
Revisions per Section 4:
- **Honest provenance:** no such pipeline exists in ECC (verified) — this is a *novel*
  design, borrowing ECC's `council` role-lens table and the GAN agents' prompt-defense
  preamble for the three passes.
- **Gate placement (C3):** the dispatcher never dispatches `@reviewer` and has no
  "design complete" detection, so there is no dispatcher exit-gate insertion point.
  The gate lives in **skill text** instead: `harness-brainstorming-plans` (this very
  skill) and `harness-requesting-code-review` require a risk report newer than the
  design doc before sign-off, with the staleness check done by a small helper the
  skill invokes. Advisory semantics, accepted in writing.
- ⚠️ The pipeline dispatches **fresh general-purpose agents with explicit
  verify-real-state instructions**, not the existing `orchestrator-plugin:adversary`
  (unreliable in this environment).

### Cross-cutting — Feature Toggles (per `harness_features_tree.md`)
Every one of the five features is independently toggleable, following the master
configuration tree in `harness_features_tree.md`. Mechanics:

- **Two-file toggle flow (operator YAML → compiled JSON):** the operator-facing file
  is a minted **`features.yaml`** — readable, commented, mirrors the tree's nesting
  (`pipeline` / `wrappers` / `services` / `agents` / `skills` / `hooks`). Deployed
  hooks are stdlib-only and can't parse YAML, so a tool-plane compile step —
  **`harness-wf features sync`** (also auto-run during `init` / `update` /
  `domain-refresh`) — compiles it to **`features.json`**, the machine-read artifact
  the loaders consume. Operators edit the YAML, never the JSON.
- **Staleness guard:** the deployed `prompt_classifier` compares mtimes (stdlib) and
  injects a one-line warning when `features.yaml` is newer than `features.json` —
  a toggled-but-unsynced file is never silently ignored.
- **Classification (M2):** `features.yaml` ⇒ **`customizable`** (3-way merge preserves
  operator toggles while delivering new keys from later phases); `features.json` ⇒
  **`generated`** (always recompiled, never hand-merged).
- **Loader:** one shared `load_features()` helper in the deployed plane's
  `hook_common.py` (already the shared-utility home for hooks), plus a tool-plane
  twin in `src/harness/init/` for init-time decisions. Lookup is by dotted path,
  e.g. `features("pipeline.dispatcher.gates.search_first")`.
- **Semantics:** missing keys default to **enabled** (fail-open) so existing deployed
  repos keep working untouched; disabling a gate makes it advisory-silent, not broken.
- **Schema + dependency validation at compile time (R3):** the features are not
  independent — F1's extraction and F4's `research_done` both live in F5's store, and
  F2 Tier 2 requires agent dispatch. `compile_features` validates the YAML against a
  declared schema (unknown keys warn, wrong types fail the sync) and a **dependency
  table** — `pipeline.dispatcher.gates.search_first → services.session_memory`,
  `hooks.session_end.learning_extraction → services.session_memory` — and **fails
  `features sync` with an explicit message** when an enabled feature's dependency is
  off (no silent auto-degrade; the operator is present at compile time and can fix
  it). Read-time fail-open is unchanged — validation happens where PyYAML and a human
  exist, enforcement of nothing happens in the stdlib loaders.
- **New keys this design adds to the tree:**
  - `rules_packs.enabled` + `rules_packs.languages.<lang>` — F3 (init-time)
  - `services.session_memory.enabled` — F5 (Stop/SessionStart persistence)
  - `hooks.session_end.learning_extraction` + `skills.continuous-learning` — F1
  - `pipeline.dispatcher.gates.search_first` + `skills.search-first` — F4
  - `pipeline.dispatcher.gates.adversary_exit` + `skills.adversary-pipeline` — F2
- `harness_features_tree.md` (this repo) remains the master documentation of the
  tree's shape; the minted per-repo `features.yaml` is the operator's toggle surface;
  the compiled `features.json` is the machine-read instance.

### The closed loop
`domain.json` stays the spine. F3 reads it at init; F5/F1 write session knowledge back
alongside it; F4/F2 gates consume both. Each phase is independently shippable,
TDD-tested, toggleable via `features.json`, and accounted for in the update plane
(in-manifest or explicitly out-of-tree).

**Key choices (revised per Section 4):**
1. Per-session JSON sidecars over SQLite (matches `tdd_<session>.json` convention; no shared-file races)
2. Digest write on `Stop` (idempotent), extraction on `SessionEnd`, `HARNESS_INTERNAL_LLM_CALL` guard + lockfile — fail-open throughout
3. F4 gate = SYSTEM STATE steering (`context_builder.py`) + deterministic `pre_tool_use` block; F2 gate = skill-text requirement; dispatcher stays routing-only
4. General-purpose agent dispatches for the adversary pipeline (plugin agents are inert here)
5. Two-file toggles: operator `features.yaml` (`customizable`) compiled by `harness-wf features sync` to `features.json` (`generated`); mtime staleness guard; fail-open defaults; one loader per plane
6. Learned skills stored out-of-repo (`~/.local/share/harness-wf/projects/<hash>/`); rules packs `paths`-scoped and namespaced; every cap has a number (8 KB digest, ≤6 injected, 220-char summaries, 30-day retention, ≥10-turn extraction threshold)
7. Second-round amendments (R1–R5): installed packs are a generated-mirror **install target** recorded in `render_context`; sticky-phase keys (`phase`/`phase_entered_at`/`phase_exit_artifact`) pulled forward from the deferred state machine into Phases 2/4 and the F4 gate keyed to persisted phase; toggle schema + dependency validation at compile; versioned memory entry schema with deterministic merge; Tier-2 budgets enforced by a `pre_tool_use` budget sidecar, not prompt text

---

## Section 2 — Alternatives Considered ✅ approved (revised per Section 4)

**One monolithic build vs. phased delivery.** Rejected building all five features in a
single effort: they touch different layers (init, hooks, dispatcher, skills) and a
monolith would be untestable and unreviewable. Chose five dependency-ordered phases,
each independently shippable.

**Five separate design docs.** Rejected: the features share one integration spine
(`domain.json`) and one toggle system, so splitting the docs would duplicate the
architecture narrative and hide the cross-feature dependencies (F1 needs F5's store;
F2/F4 share the gate mechanism). One doc, phased plan.

**SQLite for session state (the 1-pager's suggestion).** Rejected in favor of a JSON
sidecar: the existing TDD state already uses per-session JSON files under the state
root, hooks are short-lived subprocesses where SQLite adds locking/dependency overhead,
and the digest is capped-size anyway. YAGNI — revisit only if state grows multi-MB.

**Reusing `orchestrator-plugin:adversary` for the F2 pipeline.** Rejected: that agent
family is observed to hallucinate state in this environment. The pipeline instead
dispatches fresh general-purpose agents with explicit "verify real files/state before
asserting" instructions.

**Synchronous learning extraction.** Rejected: an LLM call can take tens of seconds or
fail; blocking a lifecycle hook would punish every session for an optional feature.
Extraction runs fail-open (detached background process; on failure, skip).

**Extraction triggered on `Stop`.** Rejected after adversarial review (C1): `Stop`
fires after *every response*, so Stop-triggered extraction means dozens of racing
extraction processes per session. `SessionEnd` is the correct trigger; `Stop` only
does the cheap idempotent digest write.

**Putting toggles inside `domain.json`.** Rejected: `domain.json` is the *facts*
manifest (stack, commands, business) regenerated by detection/refresh; toggles are
*operator preferences* that must survive regeneration. Separate `customizable`
`features.json` keeps the planes clean.

**Gating in the dispatcher.** Rejected after adversarial review (M1, M5, C3): the
dispatcher's output is advisory `additionalContext` the model may ignore, it has no
session id, it can't import `hook_common`, and it never dispatches `@reviewer` — so it
can neither enforce F4 nor host F2's exit gate. Gates moved to the deployed plane:
`context_builder.py` for steering, `pre_tool_use.py` for deterministic enforcement
(the same layer the TDD gate already proves out), skill text for F2's sign-off
requirement. The dispatcher stays pure routing.

**Storing learned skills inside the plugin tree.** Rejected after adversarial review
(C4): the post-update manifest re-walk absorbs them with phantom template sources,
then later verdicts them `removed-upstream`, blocking all future updates. Out-of-repo
storage (ECC v2's pattern) avoids both the update-plane conflict and cross-repo
contamination.

**Flat un-scoped rules packs.** Rejected after adversarial review (M3): un-scoped
files in `.claude/rules/` auto-load into *every* session (~5.3k tokens at ECC sizing).
Language packs carry `paths` frontmatter for lazy loading; only the small `common/`
pack is un-scoped, under a size budget.

**Deep multi-agent adversary review on every design.** Rejected after running one
(2026-06-10: ~24 min, ~194k tokens, 97 tool calls). Unbudgeted subagents consume
usage open-endedly. Replaced with the tiered model: inline council-style review by
default; budgeted multi-agent passes only for multi-subsystem designs. ECC itself
never runs subagent adversaries — its `council` is single-context.

**The 1-pager's file layout (`src/harness/orchestrator/`, `src/harness/state/`, root
`hooks/`).** Rejected: those paths don't exist. Real homes are
`src/harness/runtime/dispatcher.py` and `src/harness/templates/boilerplate/hooks/`.

**Extending the manifest walk to absorb out-of-plugin files (R1 alternative).**
Rejected: teaching `write_manifest` to walk arbitrary external paths generalizes the
exact failure mode C4 found (phantom sources, `removed-upstream` bricks). The
install-target/generated-mirror model keeps the manifest walking `plugin_dir` only and
adds one narrow, declarative concept instead.

**Gating F4 on per-prompt branch classification (R2 alternative).** Rejected: the
classifier demonstrably flips branches mid-workflow, so the deterministic
`pre_tool_use` block would key off a nondeterministic predicate — spurious blocks on
misrouted prompts, silent gate evaporation mid-planning. Persisted `phase` in the
session store is the stable predicate; this pulls the persistence half of the deferred
state machine forward and leaves only exit-condition detection deferred.

**Advisory-only Tier-2 budgets (R5 alternative).** Rejected (HITL, 2026-06-10): prompt
directives demonstrably don't self-limit (the 194k-token run *was* the advisory model
failing). The budget sidecar + `pre_tool_use` counter reuses the codebase's one proven
enforcement layer at the cost of a small mechanism; advisory wording stays only as
graceful steering before the hard wall.

---

## Section 3 — Detailed Implementation ✅ approved (revised per Section 4)

Six phases (Phase 0 is the toggle substrate the user requested; Phases 1–5 map to
F3→F5→F1→F4→F2). Every phase is TDD: each task is one bite-sized action
(failing test → minimal implementation → green → commit).

Toggles use the two-file flow: operators edit a minted `features.yaml`;
`harness-wf features sync` (tool plane, has PyYAML) compiles it to `features.json`,
which the stdlib-only deployed hooks read. A mtime staleness guard in
`prompt_classifier` warns when the YAML is newer than the compiled JSON.
`harness_features_tree.md` remains the master documentation of the tree's shape.

### Phase 0 — Feature-Toggle Substrate

| File | Action | Rationale |
|---|---|---|
| `src/harness/templates/boilerplate/features.yaml` | create | **Operator toggle surface** minted into targets; commented, mirrors `harness_features_tree.md` nesting, all keys `true`. |
| `src/harness/init/features.py` | create | Tool-plane loader + **YAML→JSON compiler** (`compile_features`) used by the `features sync` command and init-time decisions (Phase 1 pack filtering). **Validates at compile (R3):** declared key schema (unknown keys warn, wrong types fail) + dependency table (`gates.search_first → services.session_memory`, `learning_extraction → services.session_memory`); unmet dependency ⇒ sync fails with explicit message. |
| `src/harness/init/cli.py` | edit | New **`harness-wf features sync`** subcommand; auto-sync during `init` / `update` / `domain-refresh`. Compiles `features.yaml` → `features.json`. |
| `src/harness/templates/boilerplate/hooks/hook_common.py` | edit | Add `load_features(state_root)` + `feature_enabled("dotted.path", default=True)` reading the **compiled JSON** — the single deployed-plane lookup all hooks/gates use. Missing file/key ⇒ enabled (fail-open). |
| `src/harness/templates/boilerplate/hooks/prompt_classifier.py` | edit | **Staleness guard:** mtime compare (stdlib); inject one-line warning when `features.yaml` newer than `features.json`. |
| `src/harness/update/classification.py` | edit | `features.yaml` ⇒ **`customizable`** (3-way merge preserves toggles, delivers new keys); `features.json` ⇒ **`generated`** (recompiled, never merged) (M2). |
| `harness_features_tree.md` | edit | Add the five new keys (`rules_packs.*`, `services.session_memory`, `hooks.session_end.learning_extraction`, `pipeline.dispatcher.gates.search_first`, `pipeline.dispatcher.gates.adversary_exit`). |
| `tests/hooks/test_feature_toggles.py` | create | TDD: dotted lookup, fail-open defaults, malformed-file tolerance, staleness warning. |
| `tests/unit/test_features_loader.py` | create | TDD: YAML→JSON compile correctness (nesting, comments stripped, key parity), tool-plane/deployed loader parity. **R3:** unknown key warns, wrong type fails, enabled-feature-with-disabled-dependency fails compile with named dependency. |
| `tests/unit/test_cli_features_sync.py` | create | TDD: `features sync` subcommand; auto-sync on init/refresh. |
| `tests/unit/test_update_classification.py` | edit | TDD: `features.yaml` ⇒ `customizable`, `features.json` ⇒ `generated`; 3-way merge conflict case on the YAML. |
| `tests/unit/test_smart_merge.py` | edit | TDD (m3): both files survive `render_pass1` + re-mint; toggle key names avoid codex tool-mapping vocabulary (`Read`/`Write`/etc.). |

Tasks: (1) failing test: `feature_enabled` returns True with no file → (2) implement
loader in `hook_common.py` → (3) failing test: disabled key returns False → (4) dotted
traversal → (5) failing compile test (YAML→JSON parity) → (6) `compile_features` in
`init/features.py` → (7) failing schema + dependency-validation tests (R3) → (8)
schema + dependency table in `compile_features` → (9) failing CLI test → (10)
`features sync` subcommand + auto-sync → (11) failing staleness test → (12) mtime
guard in `prompt_classifier` → (13) failing classification tests → (14) classification
entries → (15) write `features.yaml` template + tree-doc keys → (16) full suite green,
commit.

### Phase 1 — F3 Stack-Aware Rules Packs

| File | Action | Rationale |
|---|---|---|
| `src/harness/templates/boilerplate/rules/packs/common/*.md` | create | Baseline pack every repo gets (security checklist, review standards). Un-scoped but size-budgeted (≤ 6 KB total). |
| `src/harness/templates/boilerplate/rules/packs/python/*.md`, `.../typescript/*.md`, `.../golang/*.md` | create | Per-language anti-patterns, test idioms, tooling rules (ported from ECC packs). **Every file carries `paths` frontmatter** (M3) for lazy loading. |
| `src/harness/init/minting_engine.py` | edit | In `mint_workspace`: after boilerplate copy, prune `rules/packs/` to `common` + stack languages, installing into `.claude/rules/harness/` (namespaced); inline packs into agent personas via `@../rules/` includes on non-Claude platforms (M3). |
| `src/harness/init/lang_aliases.py` | create | Language-aware alias map (m2): Linguist `Go`/`TypeScript` → pack dirs `golang/`/`typescript/`; ignores cdxgen framework names mixed into `stack`. |
| `src/harness/init/cli.py` | edit | `domain-refresh` path re-runs pack sync so a stack change re-selects packs. |
| `src/harness/update/manifest.py` | edit | Persist the stack filter in `render_context` (C4) **and record `.claude/rules/harness/` as an install target** (R1): path + producing pack set, so the update plane owns the mirror without walking outside `plugin_dir`. |
| `src/harness/update/classification.py` + `src/harness/update/updater.py` | edit | `enumerate_source_producers`/`compute_verdicts` respect the persisted stack filter — pruned packs are never re-proposed as `new-file` (C4). **`updater` regenerates the install-target mirror** (re-prune + re-copy from template packs, never 3-way merged) on every update, so pack content updates reach deployed repos (R1). |
| `tests/unit/test_rules_packs.py` | create | TDD: Python-only repo gets `common`+`python`, not `golang`; alias mapping; `paths` frontmatter present; toggle off ⇒ no packs. |
| `tests/unit/test_minting_engine.py` | edit | TDD: pack pruning + namespacing integrated into mint flow. |
| `tests/unit/test_update_updater.py` | edit | TDD (C4): pruned packs not re-delivered by `harness-wf update`. TDD (R1): updated pack content in the template tree DOES reach the deployed mirror on update; operator edits inside `.claude/rules/harness/` are overwritten (generated semantics, documented). |
| `tests/integration/test_template_integrity.py` | edit | Packs ship intact in the template tree. |

Tasks: (1) failing alias-map test → (2) `lang_aliases.py` → (3) failing pack-selection
test → (4) pruning function → (5) failing mint integration test → (6) wire into
`mint_workspace` → (7) failing update-plane test (pruned pack not re-proposed) → (8)
persist stack filter + verdict logic → (9) failing install-target tests (R1: mirror
regenerated on update, pack content updates delivered, operator edits overwritten) →
(10) install-target record in `manifest.py` + regenerate step in `updater.py` → (11)
failing refresh test → (12) CLI re-sync → (13) author pack content with `paths`
frontmatter (content review) → (14) suite green, commit.

### Phase 2 — F5 Session Memory

| File | Action | Rationale |
|---|---|---|
| `src/harness/templates/boilerplate/hooks/session_memory_save.py` | create | `Stop`-event hook (fires **per response** — C1): cheap idempotent overwrite of **this session's own file** `state/session_memory_<session>.json` (M6 — no shared-file races). Also wired to `PreCompact` so context survives compression. Entries follow the **R4 schema**: `{schema_version, ts, session_id, kind: decision\|blocker\|pattern\|phase, summary ≤220, refs[]}`. |
| `src/harness/templates/boilerplate/hooks/session_start.py` | create | `SessionStart`-event hook: merge per-session files into a digest at read time; inject with hard caps — **≤ 8 KB, ≤ 6 entries, ≤ 220 chars/summary, 30-day retention**; honor `HARNESS_SESSION_CONTEXT=off`. |
| `src/harness/templates/boilerplate/hooks/hook_common.py` | edit | Shared digest-cap, retention-prune, and store-path helpers (one home, both hooks use them). **Deterministic merge (R4):** recency-first, dedup on `(kind, normalized-summary)`, tie-break `(ts, session_id)` — byte-identical digest on re-read. **Phase-key helpers (R2):** `set_phase`/`get_phase`/`clear_phase` over `phase`, `phase_entered_at`, `phase_exit_artifact`. |
| `src/harness/templates/boilerplate/hooks/hooks.json` | edit | Register `Stop`/`PreCompact` → `session_memory_save.py`, `SessionStart` → `session_start.py`. |
| `src/harness/adapters/claude.py` + `src/harness/adapters/platform_profiles.json` | edit | Claude wiring is full support. Gemini: add `Stop`/`SessionStart` to `event_mappings` **only after verifying Gemini CLI equivalents exist**; codex/cursor/generic have no hook runtime — documented Claude-first matrix (M4). |
| `tests/hooks/test_session_memory.py` | create | TDD: write→read round-trip, per-session isolation (two concurrent sessions don't clobber), cap + retention enforcement, corrupt-store tolerance, opt-out env, toggle-off ⇒ no-op. **R4:** schema_version present in every entry, deterministic digest (two reads ⇒ byte-identical), unknown-schema-version entries skipped not crashed. **R2:** phase keys round-trip via the helpers. |
| `tests/integration/test_claude_plugin_contract.py` | edit | New hooks present + wired in minted plugin. |

Tasks: (1) failing schema round-trip test (R4) → (2) `session_memory_save.py` minimal
write with schema'd entries → (3) failing concurrent-session isolation test → (4)
per-session file naming → (5) failing deterministic-merge test (R4: byte-identical
re-read) → (6) merge + dedup in `hook_common` → (7) failing cap/retention test → (8)
cap logic in `hook_common` → (9) failing phase-key tests (R2) → (10)
`set_phase`/`get_phase`/`clear_phase` helpers → (11) failing injection test → (12)
`session_start.py` merge-at-read → (13) failing wiring test → (14) `hooks.json` +
adapter mapping (Claude; gemini pending verification) → (15) opt-out + toggle-off
tests + gates → (16) suite green, commit.

### Phase 3 — F1 Continuous Learning

| File | Action | Rationale |
|---|---|---|
| `src/harness/templates/boilerplate/scripts/extract_skills.py` | create | Reads session transcript, calls LLM via the runtime client minted by `copy_runtime_modules`, writes `SKILL.md` files (with confidence + dedup frontmatter) to **`~/.local/share/harness-wf/projects/<repo-hash>/learned/<slug>/`** — out-of-repo (C4, ECC v2): invisible to the update manifest, no cross-repo contamination. Separate script so the hook stays thin. |
| `src/harness/templates/boilerplate/hooks/session_end.py` | create | **`SessionEnd`-event** hook (C1 — not Stop): spawn `extract_skills.py` detached when `hooks.session_end.learning_extraction` is on. **Guards (C2):** exit immediately if `HARNESS_INTERNAL_LLM_CALL=1`; lockfile prevents overlapping extractions; skip sessions < 10 turns. **Fail-open**: any failure logs and exits 0. |
| `src/harness/templates/boilerplate/hooks/session_start.py` | edit | Inject ≤ 6 learned-skill summaries (220-char) from the out-of-repo store alongside the Phase 2 digest. |
| `src/harness/templates/boilerplate/hooks/hooks.json` | edit | Register `SessionEnd` → `session_end.py`. |
| `src/harness/templates/boilerplate/skills/continuous-learning/SKILL.md` | create | `/learn` on-demand trigger for the same extraction path mid-session. |
| `src/harness/templates/boilerplate/skills.json` | edit | Register the new skill. |
| `tests/unit/test_skill_extraction.py` | create | TDD (LLM mocked): transcript→SKILL.md shape, slug/confidence/tag correctness, repo-hash store path, dedup against existing learned skills. |
| `tests/hooks/test_session_end_learning.py` | create | TDD: detached spawn, **`HARNESS_INTERNAL_LLM_CALL` guard short-circuits (C2)**, lockfile exclusion, min-session threshold, fail-open on LLM error/timeout, toggle-off ⇒ skipped. |

Tasks: (1) failing internal-call-guard test → (2) guard + lockfile in `session_end.py`
→ (3) failing extraction-shape test → (4) `extract_skills.py` with mocked LLM → (5)
failing out-of-repo-path + dedup tests → (6) store path + dedup → (7) failing
min-session + fail-open tests → (8) spawn logic → (9) failing injection-cap test →
(10) `session_start.py` learned-skill injection → (11) author `/learn` SKILL.md +
register → (12) suite green, commit.

### Phase 4 — F4 Search-First Gate

| File | Action | Rationale |
|---|---|---|
| `src/harness/runtime/context_builder.py` | edit | **The SYSTEM STATE block is assembled here** (m1 — not in `prompt_classifier.py`): add the gate-status line for Branch B when `research_done` is unset. Steering layer. Dispatcher untouched — it stays routing-only (M5). |
| `src/harness/templates/boilerplate/hooks/prompt_classifier.py` | edit | Only its inline fallback SYSTEM STATE needs the same line (m1). |
| `src/harness/templates/boilerplate/hooks/pre_tool_use.py` | edit | **Enforcement layer (M1, R2):** block the first source-file write **while persisted `phase=planning`** (read via Phase 2's `get_phase` — NOT per-prompt branch classification, which flips mid-workflow) until `research_done` is set — same deterministic mechanism as the existing TDD gate, gated by `pipeline.dispatcher.gates.search_first`. No persisted phase ⇒ passthrough. |
| `src/harness/templates/boilerplate/skills/harness-brainstorming-plans/SKILL.md` | edit | **Phase producer (R2):** first act on entry sets `phase=planning` + `phase_entered_at` in the session store; sign-off/hand-off clears it (recording `phase_exit_artifact` = the design doc path). This is the minimal pulled-forward slice of follow-up #1. |
| `src/harness/templates/boilerplate/skills/search-first/SKILL.md` | create | Structured research workflow. **Step 1 = proportionality check / waiver hatch:** known approach or well-trodden ground ⇒ one-line waiver, set `research_done`, exit. Otherwise: enumerate unknowns → research → ECC's **Adopt / Extend / Compose / Build** matrix → cited findings doc → set `research_done`. |
| `src/harness/runtime/dispatcher.py` | edit | **Bias-to-D rule in the `classify_intent` prompt** (`:149`): uncertain B-vs-D ⇒ D; B reserved for genuinely open design work. (Prompt text only — routing logic untouched.) |
| `src/harness/templates/boilerplate/hooks/prompt_classifier.py` | edit | Same bias-to-D rule in the fallback heuristics; D pre-flight guidance: missing context ⇒ ask the user 1–2 clarifying questions, never escalate to B. |
| `src/harness/templates/boilerplate/skills.json` | edit | Register the skill. |
| `tests/unit/test_context_builder.py` | edit | TDD: Branch B + no flag ⇒ gate line in SYSTEM STATE; flag set or toggle off ⇒ no line. |
| `tests/unit/test_dispatcher.py` + `tests/unit/test_fallback_classify.py` | edit | TDD: ambiguous implement-style prompts classify D, not B; clear design-work prompts still classify B. |
| `tests/unit/test_pre_tool_use_tdd.py` / `tests/hooks/test_search_first_gate.py` | edit / create | TDD: source write blocked while `phase=planning` without flag; allowed with flag; **classification flip mid-phase does NOT drop the gate; no persisted phase ⇒ passthrough (R2)**; toggle off ⇒ passthrough; waiver path sets flag; no interference with the TDD gate. |

Tasks: (1) failing context-builder test → (2) gate line → (3) failing pre_tool_use
block test keyed to persisted phase (R2: includes classification-flip and no-phase
cases) → (4) enforcement check via `get_phase` → (5) failing phase-producer test
(brainstorming skill sets/clears phase) → (6) phase set/clear in skill text +
contract test → (7) failing bias-to-D classification tests → (8) classifier prompt +
fallback edits → (9) failing toggle-off + TDD-coexistence + waiver tests → (10)
toggle wiring → (11) author SKILL.md (waiver step + adopt/extend/compose/build) +
register → (12) suite green, commit.

### Phase 5 — F2 Adversary Pipeline

| File | Action | Rationale |
|---|---|---|
| `src/harness/templates/boilerplate/skills/adversary-pipeline/SKILL.md` | create | **Tiered:** Tier 1 (default) = inline council-style role-lens review, no subagents. Tier 2 (opt-in) = three sequenced passes — Attacker → Defender → Auditor — each a **fresh general-purpose dispatch** with explicit "verify real files/state before asserting" instructions and budgets (≤30 tool calls, ≤12 files, smaller model for Attacker/Defender, degrade-gracefully clause). **Before each dispatch the skill writes the budget sidecar (R5)** so the limits are enforced, not requested. Borrows ECC council's role-lens table + GAN agents' prompt-defense preamble (this pipeline is novel, not an ECC port). Auditor writes `docs/adversary/YYYY-MM-DD-<topic>-risk-report.md`. |
| `src/harness/templates/boilerplate/hooks/pre_tool_use.py` | edit | **Budget backstop (R5):** when `state/budget_<session>.json` exists, count tool calls / file reads against its limits; past the limit ⇒ block (exit 2) with "budget reached — summarize what you have and finish." No sidecar ⇒ passthrough (zero cost to normal sessions). Stale sidecars pruned by the Phase 2 retention helper. |
| `src/harness/templates/boilerplate/scripts/check_risk_report.py` | create | Staleness helper invoked by skill text: risk report exists and is newer than the design doc (mtime compare). No dispatcher involvement — the `@reviewer` dispatch point doesn't exist there (C3). |
| `src/harness/templates/boilerplate/skills/harness-brainstorming-plans/SKILL.md` + `.../harness-requesting-code-review/SKILL.md` | edit | **Skill-text gate (C3):** before sign-off/hand-off, when `pipeline.dispatcher.gates.adversary_exit` is on, require a fresh risk report via `check_risk_report.py`. Advisory semantics, accepted in writing. |
| `src/harness/templates/boilerplate/agents/adversary.md` | edit | Re-scope persona as the Auditor role description referenced by the pipeline (not a standalone single pass). |
| `src/harness/templates/boilerplate/skills.json` | edit | Register the skill. |
| `tests/unit/test_adversary_pipeline.py` | create | TDD: report path/naming, staleness comparison vs design doc mtime, toggle-off ⇒ checker reports pass. |
| `tests/hooks/test_dispatch_budget.py` | create | TDD (R5): counter increments per tool call; block past limit with summarize-and-finish message; no sidecar ⇒ passthrough; corrupt sidecar ⇒ fail-open passthrough; per-session isolation (one session's budget never throttles another). |
| `tests/integration/test_claude_plugin_contract.py` | edit | New skill present in minted plugin; gate text present in the two edited skills. |

Tasks: (1) failing staleness-checker test → (2) `check_risk_report.py` → (3) failing
budget-backstop tests (R5: increment, block, no-sidecar passthrough, fail-open) →
(4) sidecar counting + block in `pre_tool_use.py` → (5) failing toggle-off test →
(6) toggle wiring → (7) author pipeline SKILL.md (writes sidecar before each Tier-2
dispatch) + persona edit → (8) add gate text to the two skills + contract test →
(9) suite green, commit.

### Cross-phase invariants
- After every phase: `python3 -m pytest` and `python3 -m pytest tests/integration`
  fully green (per `domain_ops("test")`).
- Every new boilerplate file is **accounted for in the update plane** (C4): in-manifest
  with correct classification (`features.json` ⇒ `customizable`; packs ⇒ stack-filtered
  producers) or explicitly out-of-tree (learned skills in `~/.local/share/harness-wf/`).
  Covered by `tests/unit/test_update_manifest.py` + the Phase 1/3 update-plane tests.
- Context budget: every injection has a number (8 KB digest, ≤ 6 entries, ≤ 6 learned
  skills, 220-char summaries, ≤ 6 KB un-scoped `common/` pack); no adjective-only caps.
- Platform matrix: F3/F4/F2 all platforms (inline includes where no auto-load);
  F5/F1 Claude-first (gemini pending event verification; codex/cursor/generic no hook
  runtime).
- Each phase ends with a version-stamped commit; phases are independently revertible.
- **Dependency edges added by R1/R2 (Section 5):** Phase 1's update-plane work
  implements the install-target mechanism specced here (no further design needed);
  Phase 4's gate consumes Phase 2's phase keys — Phase 4 cannot start before Phase 2's
  R2 helpers land. Phase ordering F3→F5→F1→F4→F2 already satisfies both.

---

## Follow-ups (post-review discussion, 2026-06-10)

Captured from HITL discussion after the design was committed; folded into Phase 5
above where applicable, deferred where noted.

1. **Sticky phase state machine (deferred — candidate "Phase 6", separate design).**
   The current dispatch model is stateless per-prompt re-classification: every prompt
   re-derives branch/agent and injects a fresh dispatch suggestion, so mid-workflow
   prompts get misrouted (observed repeatedly in the design session itself: B → E → C
   flips mid-skill, and dispatch directives issued while a skill was already running).
   The fix is a *sticky* phase: once planning (or TDD execution) starts, persist
   `phase` in the session-state store (Phase 2's F5 substrate provides exactly this)
   and shrink the classifier's job to "still in phase? / did an exit condition fire?".
   This also completes what Section 4 C3 found missing: artifact-based phase-completion
   detection. Out of scope for this design — needs its own HITL pass — but Phases 2/4
   should be built with this consumer in mind (state keys: `phase`, `phase_entered_at`,
   `phase_exit_artifact`).
   **Amended per R2 (Section 5):** the *persistence half* is no longer deferred — the
   three state keys, the `set_phase`/`get_phase`/`clear_phase` helpers (Phase 2), and
   the brainstorming skill setting/clearing `phase` (Phase 4) ship in this design,
   because F4's deterministic gate cannot key off per-prompt classification. What
   remains deferred to Phase 6: exit-condition *detection* (artifact-based phase
   completion) and shrinking the classifier's role.

2. **Subagent usage guardrails (adopted into Phase 5).** Observed one unbudgeted
   review agent consume ~194k tokens / 97 tool calls / 24 min. All agent dispatches
   defined by this design now carry budgets in the dispatch prompt: max tool calls,
   max files read, model tier, and a degrade-gracefully clause ("summarize what you
   have and stop"). Long-running dispatches run backgrounded.

3. **Tiered adversary review (adopted into Phase 5).** Tier 1 inline council-style
   role lenses by default (ECC `council` pattern); Tier 2 budgeted multi-agent passes
   only for designs spanning multiple subsystems.

4. **Branching impact of the closed loop (clarified, no change).** The loop lives
   inside Branch B (F4 gates entry, F2 gates exit); F5/F1 are branch-agnostic
   lifecycle hooks; F3 is init-time. Branch topology is unchanged — but Branch B
   acquires entry/exit conditions, i.e. the embryo of follow-up #1's state machine.

5. **Proportionality / bias-to-D (adopted into Phase 4).** Branch B's pipeline is for
   large open design work; simple already-decided implementations must route to
   Branch D, which asks clarifying questions instead of researching. Adopted as:
   bias-to-D rule in the `classify_intent` prompt + fallback heuristics, and a
   waiver escape hatch as step 1 of the search-first skill.

6. **Operator toggle surface (adopted into Phase 0).** Toggling lives in a minted
   per-repo `features.yaml` (human-edited), compiled to `features.json` by
   `harness-wf features sync`, with a deployed mtime staleness warning. Previously
   the design had operators editing the JSON directly.

---

## Section 4 — Adversarial Review Notes

*Reviewed 2026-06-10 against the real tree (HEAD = 8dc28f3) and the live ECC repo
(github.com/affaan-m/ECC, fetched via `gh api` 2026-06-10). Every claim below was
checked against an actually-read file or fetched URL; anything unverifiable is
labeled UNVERIFIED.*

### Verified claims

- **Two-plane layout is real.** `src/harness/templates/boilerplate/` is copied at init
  (`src/harness/init/minting_engine.py:40-41`), the runtime slice is copied/rewritten by
  `copy_runtime_modules` (`minting_engine.py:457-515`, map at
  `src/harness/init/runtime_slice.py:43-58` — `llm_client.py` IS in the deployed slice, so
  Phase 3's "LLM via the runtime client minted by copy_runtime_modules" is plausible).
- **JSON-sidecar convention exists.** TDD state is per-session JSON at
  `state/tdd_<session>.json` (`templates/boilerplate/hooks/pre_tool_use.py:42-64`); SQLite
  rejection matches reality.
- **`hook_common.py` is the shared-utility home** (`resolve_plugin_root`, `get_session_id`,
  `capped_text` — `templates/boilerplate/hooks/hook_common.py:9-51`); adding `load_features`
  there fits. `features.json`-not-YAML is right: deployed hooks are stdlib-only subprocesses.
- **`domain.json → stack` is a flat list of strings** (`src/harness/domain/detect.py:168-182`;
  live instance `.claude/harness-wf-plugin/domain/domain.json` has `"stack": ["Python"]`).
  Pack selection by stack is feasible.
- **`domain-refresh` CLI path exists** (`src/harness/init/cli.py:235`, `:458`).
- **All referenced test files exist** (`tests/unit/test_dispatcher.py`,
  `test_minting_engine.py`, `test_update_classification.py`, `test_update_manifest.py`,
  `tests/integration/test_template_integrity.py`, `test_claude_plugin_contract.py`;
  `tests/hooks/` exists for the new hook tests).
- **The Section 1 correction of the 1-pager is itself correct**: `src/harness/orchestrator/`
  and `src/harness/state/` do not exist; `src/harness/domain/detect.py` does.
- **`adversary.md` persona exists to re-scope** (`templates/boilerplate/agents/adversary.md`).
- **`harness_features_tree.md` exists at repo root** and already contains
  `pipeline/wrappers/services/agents/skills` nesting matching the design's loader paths.

### Findings (prioritized)

#### Critical

1. **C1 — `Stop` is per-response, not session end; the Phase 2/3 premise is wrong.**
   The design treats `Stop` as "session end" ("serialize key decisions… never block
   session end"). In Claude Code, `Stop` fires after **every** assistant response;
   `SessionEnd` is the end-of-session event. ECC itself documents this:
   `hooks/hooks.json` id `stop:session-end` is described as "Persist session state
   **after each response** (Stop carries transcript_path)", and it has a separate
   `SessionEnd` lifecycle marker (ECC `hooks/hooks.json`, fetched). Consequence for F1:
   the "extraction step on Stop" spawns a detached LLM extraction **per turn**, not once
   per session — dozens of redundant, racing extraction processes per working session.
   Phase 2's store-write per turn is survivable (idempotent overwrite) but Phase 3 as
   specced is not. Fix: write the digest on `Stop` (cheap, idempotent) but trigger
   extraction on `SessionEnd` (or debounce/lockfile on Stop).

2. **C2 — Recursion/spawn loop in F1 extraction.** `extract_skills.py` is to call the
   minted LLM client; `query_llm` shells out to the platform CLI
   (`src/harness/runtime/llm_client.py:58-60` runs `claude --output-format=json -p -`).
   A headless `claude -p` run in the same repo executes the repo's hooks — including the
   new `Stop` hook — which spawns `extract_skills.py` again. `llm_client` sets
   `HARNESS_INTERNAL_LLM_CALL=1` (`llm_client.py:46`) but **no hook anywhere consumes it**
   (grep over `src/` finds exactly one occurrence: the setter). Without an explicit guard
   in `session_end.py` (skip when `HARNESS_INTERNAL_LLM_CALL=1`), the design's fail-open
   detached spawn is an unbounded process bomb. The doc never mentions this guard.

3. **C3 — F2's "Branch-B exit gate before `@reviewer` dispatch" has no insertion point.**
   The dispatcher never dispatches a reviewer: `BRANCH_ROUTING` maps B → `planner` only
   (`src/harness/runtime/dispatcher.py:95-101`), and `evaluate_artifacts` assigns a
   **static** phase string per branch — Branch B is always `"Planning/Execution"`
   (`dispatcher.py:315-322`); there is no "design complete" detection anywhere.
   Reviewer hand-off happens inside skill text (e.g. `harness-brainstorming-plans`), which
   the dispatcher cannot see. Implementing "when design complete, require a fresh risk
   report before @reviewer" requires building phase detection from artifacts —
   a new mechanism, not the "edit" the Phase 5 table claims. Either gate it inside the
   brainstorming/review skill text (advisory) or design the artifact-based phase machine
   explicitly.

4. **C4 — Update-manifest machinery actively fights two of the new artifact types.**
   - *Pruned rules packs get re-delivered forever.* `enumerate_source_producers` walks the
     **entire** `templates/boilerplate/rules/` tree (`src/harness/update/classification.py:178-189`)
     and `compute_verdicts` marks any producer absent from the deployed manifest as
     `new-file` to deliver (`src/harness/update/updater.py:98-103`). A Python-only repo with
     `golang/` pruned at mint gets the golang pack re-proposed by every `harness-wf update`.
     Pack pruning needs stack-awareness in the update plane (e.g. persist the stack filter in
     `render_context`, `manifest.py:114-118`), which the design never mentions.
   - *Learned skills can brick `update`.* If learned `SKILL.md`s land under the plugin's
     `skills/` dir (and on embedded platforms like gemini the config dir IS the deployed
     root), the post-update `write_manifest` re-walk absorbs them as owned-customizable with
     a phantom template source (`classification.py:151-155`, `manifest.py:92-112`); the next
     update computes `removed-upstream` (`updater.py:132-134`), which **blocks the whole
     update** for customizable files unless `--force` (`updater.py:182-188`). The design's
     `.claude/skills/learned/` path dodges this on Claude only by living outside the plugin
     dir — which then breaks the doc's own invariant that "every new minted file lands in
     the update manifest" (the manifest walks `plugin_dir` only, `manifest.py:92`). Neither
     half is resolved in the doc.

#### Major

5. **M1 — "Enforced exactly like today's TDD gate" misdescribes the architecture.** The TDD
   gate is a **hard block** in `pre_tool_use.py` (`_check_tdd`,
   `templates/boilerplate/hooks/pre_tool_use.py:67-87`, exit code 2). The dispatcher enforces
   nothing: its output becomes an advisory "HARNESS DISPATCH" directive appended to
   `additionalContext` (`src/harness/adapters/claude.py:177-200`), which the model may
   ignore. There is also no "existing artifact gating" to copy: `missing_documents` is
   initialized and returned but never populated (`dispatcher.py:292`, `:329`). F4 as
   designed is *steering*, not *enforcement* — acceptable, but the doc's equivalence claim
   is false, and Section 2's rejection of `pre_tool_use` placement gives away the only
   deterministic enforcement point the codebase actually has.

6. **M2 — "user-owned" is not a classification that exists.** `classification.py` knows
   `generated | customizable | derived` (`src/harness/update/classification.py:6-9, 30-34`).
   The real choice for `features.json` is: (a) leave it **unclassified** → `classify()`
   returns `None` (`classification.py:157-158`) → update never touches it, but also can
   never deliver new toggle keys added by Phases 1-5; or (b) classify **customizable** →
   3-way merge via the base sidecar (`manifest.py:134-148`), which preserves user edits AND
   delivers new keys, at the cost of possible conflicts. The design needs to pick (b) and
   say so; "classify user-owned" as written maps to nothing in the API.

7. **M3 — Rules-pack consumption is unspecified and platform-divergent.** Verified
   mechanics: deployed plugin `rules/*.md` are consumed two ways — inlined into agent
   personas via `@../rules/*.md` includes at mint (`templates/boilerplate/agents/*.md:29-34`,
   `process_includes` in `minting_engine.py:110-126`) and exported to `rules.json`
   (`plugin_generator.py:213-240`), which the dispatcher loads **and never uses**
   (`dispatcher.py:112`, `:140-146` — load-only, zero readers). If packs land in the plugin
   `rules/` dir they are dead weight. If they land in **`.claude/rules/`** as the design
   literally says, Claude Code auto-loads every non-path-scoped file at launch
   (verified: code.claude.com/docs/en/memory, "Rules without `paths` frontmatter are loaded
   at launch") — that works on Claude, costs context (see below), is invisible to the
   update manifest (C4), and has no equivalent on gemini/codex/generic
   (`.gemini/rules/` is not auto-loaded by anything; cursor uses `.cursor/rules` with its
   own format). The design must name the consumption mechanism per platform; ECC solves
   this with `paths` frontmatter on every language file (verified:
   `rules/python/coding-style.md` opens with `paths: ["**/*.py", "**/*.pyi"]`).

8. **M4 — Stop/SessionStart wiring beyond Claude doesn't exist and partially can't.**
   `templates/boilerplate/hooks/hooks.json` currently wires only
   UserPromptSubmit/PreCompact/PreToolUse/PostToolUse (`hooks.json:2-52`). Per-platform:
   gemini's `event_mappings` covers exactly those four events
   (`src/harness/adapters/platform_profiles.json:46-51`) — its `install_hooks` only rewrites
   event names present in that map (`src/harness/adapters/gemini.py:47-59`), so unmapped
   `Stop`/`SessionStart` keys would deploy verbatim and silently never fire (whether Gemini
   CLI has equivalents: UNVERIFIED). codex/cursor/generic have **empty** `event_mappings`
   (`platform_profiles.json:89, 127, 146`) and their `install_hooks` only rewrites paths
   (`codex.py:39-57`) — codex has no hook runtime at all in this codebase. F5/F1 are
   effectively Claude-only at launch; the doc's "other adapters if event names differ" is an
   understatement that should become an explicit platform-support matrix.

9. **M5 — Loader duplication is three-way, not two-way.** Phases 4/5 put toggle checks in
   `dispatcher.py`. In the tool plane, `src/harness/runtime/dispatcher.py` cannot import
   `hook_common` (it lives in `templates/boilerplate/hooks/`, not on any import path), so
   `tests/unit/test_dispatcher.py` will exercise a dispatcher that needs its own
   feature-loading fallback. Deployed, it works only by accident of `sys.path` (hook scripts
   run with `hooks/` as script dir; `prompt_classifier.py:104-112` adds plugin `src/` too).
   That is a third loader site with drift risk, contradicting "one shared loader per plane."
   Same problem for the gate's session-state read: `evaluate_artifacts` has no session id
   and `get_session_id` lives in `hook_common` (`hook_common.py:29-44`). Cleanest fix: do
   the gate check in `prompt_classifier`/`context_builder` (deployed plane), keep
   `dispatcher.py` pure routing.

10. **M6 — Single-file `session_memory.json` collides with the multi-session reality the
    doc itself targets.** Existing state is per-session (`tdd_<session>.json`,
    `pre_tool_use.py:42-43`); `get_session_id` falls back to `os.getppid()`
    (`hook_common.py:44`), so two concurrent engineers (the doc's stated audience:
    "teams… across shifts") produce interleaved read-modify-write on one JSON file with no
    locking — same lost-update pattern `campaign_state.json` already has
    (`prompt_classifier.py:157-186`). Spec per-session files merged into a digest at read
    time, or O_APPEND journal + compaction. ECC handles this with session leases
    (`scripts/hooks/session-start.js` → `writeSessionLease`).

#### Minor

11. **m1 — Wrong file for the SYSTEM STATE edit.** The block is assembled in
    `src/harness/runtime/context_builder.py:27-55` (a runtime-slice file), not in
    `prompt_classifier.py` (which only calls it, `prompt_classifier.py:192-203`; its inline
    fallback at `:205-211` would also need the line). Phase 4's table edits the wrong file.
12. **m2 — Language naming mismatch.** Linguist/detection emits `"Go"`, `"Python"`,
    `"TypeScript"` (`detect.py:21-27`); the pack dirs are `golang/`, `python/`,
    `typescript/`. A case/alias map is needed; `stack` also mixes in cdxgen framework names
    (`detect.py:174-182`), so matching must be language-aware, not substring.
13. **m3 — `features.json` will pass through `render_pass1` and smart-merge.** Minting
    rewrites all `.json` files (`minting_engine.py:79-92`) and `perform_smart_merge`
    deep-merges JSON on re-mint (`minting_engine.py:270-322`, `:401-427`). Mostly benign
    (deep merge preserves user keys) but worth a test: codex tool-mapping rewrites
    (`platform_profiles.json:69-88`) substitute words like `Read`/`Write` inside any file
    content — keep toggle key names out of that vocabulary.
14. **m4 — Native overlap unaddressed.** Claude Code now ships project-scoped auto-memory
    (MEMORY.md, 200-line/25KB cap — code.claude.com/docs/en/memory) which overlaps F5/F1 on
    the design's primary platform. The cross-platform/team-shared rationale for building a
    parallel store is real but unstated; double-injection (auto-memory + session digest)
    should be considered.

### ECC comparison

(Repo verified: `gh repo view affaan-m/ECC` — "Skills, instincts, memory, security, and
research-first development for Claude Code, Codex, Opencode, Cursor and beyond." All file
citations below were fetched from the repo on 2026-06-10.)

- **F1 Continuous learning.** The design ports ECC's **v1** shape (Stop-hook transcript →
  `skills/learned/` SKILL.md) — which ECC explicitly **deprecated**
  (`skills/continuous-learning/SKILL.md`: "[DEPRECATED - use continuous-learning-v2]…").
  v2.1 (`skills/continuous-learning-v2/SKILL.md`) observes via PreToolUse/PostToolUse hooks
  ("100% reliable" vs Stop), extracts atomic **instincts** with confidence scores (0.3-0.9)
  via a background Haiku agent, stores them **outside the repo**
  (`~/.local/share/ecc-homunculus/projects/<hash>/`), scopes per-project with promotion to
  global after 2+ projects, and supports export/import. Dropped by the design: confidence
  scoring, instinct granularity, project-scope contamination control, out-of-repo storage
  (which would incidentally dodge finding C4), v1's `min_session_length: 10` guard, and
  curation commands. Worth adopting: at minimum the out-of-repo store, a min-session
  threshold, and confidence/dedup metadata.
- **F2 Adversary pipeline.** **No Attacker→Defender→Auditor pipeline exists in ECC** as far
  as code search shows (`gh api search/code q=attacker|defender` hits only the security
  guides and rule prose). ECC's closest analogs: `skills/council/SKILL.md` (4 voices:
  Architect/Skeptic/Pragmatist/Critic, for decisions not designs), `skills/security-review`
  (checklist skill), and the GAN trio (`agents/gan-planner.md`/`gan-generator`/
  `gan-evaluator` — build-and-evaluate, not attack). F2 is therefore a novel design, not a
  port; the doc should stop implying ECC parentage and may borrow council's
  explicit role-lens table and the GAN agents' prompt-defense preamble
  (`agents/gan-planner.md` "Prompt Defense Baseline") for the three dispatched passes.
- **F3 Rules packs.** Structure matches ECC (`rules/common/` + 18 language dirs,
  `rules/README.md`). Three things ECC does that the design misses: (1) **`paths`
  frontmatter on every language file** so packs only enter context when matching files are
  touched (verified `rules/python/coding-style.md`); (2) a **namespace dir**
  (`.claude/rules/ecc/`) to avoid collisions with user rules, plus an explicit warning that
  flattening breaks same-named files across packs; (3) layered precedence
  (language overrides common, with cross-references). The design's stack-driven selection
  is a genuine improvement over ECC's manual `./install.sh python`.
- **F4 Search-first.** ECC's `skills/search-first/SKILL.md` is a *decision workflow* —
  tool-availability preflight, parallel registry/MCP/GitHub research via a researcher
  agent, then an **Adopt / Extend / Compose / Build** decision matrix. It is not a planner
  gate. ECC's actual *enforcement* analog is the `gateguard-fact-force` PreToolUse hook
  ("block first Edit/Write/MultiEdit per file and demand investigation", `hooks/hooks.json`).
  The design's branch-entry gate is a deliberate hybrid, but it drops the adopt/extend/build
  matrix (the highest-value part — it prevents writing code at all) and chooses the
  non-enforcing layer (see M1) while ECC demonstrates the enforcing one.
- **F5 Session memory.** ECC's contract (`hooks/memory-persistence/README.md`) is richer:
  SessionStart loads **bounded** prior context with hard numbers
  (`scripts/hooks/session-start.js`: `DEFAULT_SESSION_START_CONTEXT_MAX_CHARS = 8000`,
  `MAX_INJECTED_INSTINCTS = 6`, `MAX_INJECTED_LEARNED_SKILLS = 6`,
  `MAX_LEARNED_SKILL_SUMMARY_CHARS = 220`, `DEFAULT_SESSION_RETENTION_DAYS = 30`), plus
  **PreCompact** state save, a true `SessionEnd` marker, opt-outs
  (`ECC_SESSION_START_CONTEXT=off`), and session leases for concurrency. The design has
  "capped digest" with no numbers, no retention, no PreCompact hook, no opt-out env, no
  concurrency story (M6).

### Context-window impact

Per-turn / per-session additions in deployed repos (≈4 chars/token):

| Addition | When | Size (est.) | Cap specified? |
|---|---|---|---|
| Gate status lines in SYSTEM STATE (F4+F2) | every prompt | +2-4 lines ≈ 20-50 tok on top of today's ~100-200-tok block (`context_builder.py:33-53`; business already capped at 600 chars, `context_builder.py:4`) | implicit (small) — fine |
| Session-memory digest (F5) | SessionStart, once/session | unspecified; ECC default 8 KB ≈ **2,000 tok** | **NO — needs hard byte/entry caps** |
| Rules packs in `.claude/rules/` (F3) | **every session at launch** (auto-loaded when un-scoped — code.claude.com/docs/en/memory) | ECC sizing: common ≈ 16.3 KB + python ≈ 4.8 KB ≈ 21 KB ≈ **~5,300 tok** | **NO — needs `paths` scoping + per-pack size budget** |
| New skills.json entries (3 skills) | n/a directly — skills.json is a pointer file (`dispatcher.py:243-259`); on Claude each plugin SKILL.md description enters the skill index ≈ 30-60 tok each | ~100-200 tok total | fine |
| Learned SKILL.md accumulation (F1) | each learned skill's frontmatter description joins the per-session skill index | ~30-80 tok **per skill, unbounded**; 50 skills ≈ 2-4k tok permanent + selection noise | **NO — needs max-count, retention, confidence threshold (ECC: inject ≤6, 220-char summaries, 30-day retention)** |
| `session_memory.json` / risk reports on disk | not loaded into context unless read | 0 | n/a |

The two unbounded items (un-scoped rules packs, learned-skill accumulation) dominate:
together they can quietly add ~7-9k tokens to every session — several times the cost of
everything the harness currently injects. Both need numbers in Section 3, not adjectives.

### Recommendations

1. Rewrite Phase 2/3 around correct lifecycle semantics: digest write on `Stop`
   (idempotent), extraction on `SessionEnd` (or a debounced/locked Stop), and an explicit
   `HARNESS_INTERNAL_LLM_CALL` guard in `session_end.py` before anything spawns the CLI (C1, C2).
2. Store learned artifacts **outside the deployed plugin tree** (ECC v2 pattern) or add an
   explicit `EXCLUDE_GLOBS`/classification carve-out for `skills/learned/**`; persist the
   stack filter in the manifest `render_context` and teach
   `enumerate_source_producers`/`compute_verdicts` to respect it (C4).
3. Replace "user-owned" with the real mechanism: classify `features.json` **customizable**
   (3-way merged, new keys deliverable) and add the conflict test (M2).
4. Phase 4/5 gates: put the check + SYSTEM STATE line in
   `context_builder.py`/`prompt_classifier.py`, keep `dispatcher.py` routing-only, and
   either accept advisory semantics in writing or add a `pre_tool_use` enforcement arm
   (block first source-write in Branch B until `research_done`) — that is the only
   deterministic layer that exists (M1, M5). Drop or redesign the F2 "exit gate before
   @reviewer" — the dispatch point doesn't exist (C3).
5. F3: adopt ECC's `paths` frontmatter on every language pack, a namespace subdir, and a
   per-platform consumption matrix (Claude `.claude/rules/` auto-load; others explicit);
   decide and document who owns updates for files outside the plugin dir (M3, C4).
6. Put numbers on every cap in Section 3: digest ≤ 8 KB / N entries, learned skills ≤ K
   injected + retention days + min-session threshold, pack budget per language (Context
   table above).
7. Add a platform-support matrix for F5/F1 (Claude: yes; gemini: pending event-mapping
   verification; codex/cursor/generic: no hook runtime today) instead of "other adapters
   if event names differ" (M4).

---

## Section 5 — Second-Round Review Amendments (R1–R5)

*External review received 2026-06-10, after the Section 4 revisions were folded in.
Verdict: "Mostly yes… I would not implement it unchanged. The rules-pack update
ownership and Branch-B state tracking are architectural blockers. Toggle
schema/dependencies, memory data format, and Tier-2 budget enforcement also need
specification." All five resolved below and folded into Sections 1–3 inline (tagged
R1–R5); budget enforcement choice HITL-approved 2026-06-10.*

### R1 — Rules-pack update ownership (blocker) → generated-mirror install target

The post-C4 design still contradicted itself: packs install to
`.claude/rules/harness/` (outside the plugin dir), the manifest walks `plugin_dir`
only, and the C4 fix only stopped re-delivery of *pruned* packs — nobody owned
*updates to installed* packs. **Resolution:** the installed dir is a **generated
mirror** of the in-manifest template packs, recorded in `render_context` as an
**install target**, regenerated (re-prune + re-copy, never 3-way merged, never
operator-edited) on every `init` / `update` / `domain-refresh`. Rejected alternative:
extending the manifest walk to external paths (generalizes the C4 failure mode).
Folded into: Phase 1 narrative + table (`manifest.py`, `updater.py`,
`test_update_updater.py`).

### R2 — Branch-B state tracking (blocker) → sticky-phase persistence pulled forward

F4's deterministic gate was keyed to "Branch B," a per-prompt classification that
observably flips mid-workflow — spurious blocks and silent gate evaporation.
**Resolution:** partially un-defer follow-up #1. Phase 2 ships the
`phase`/`phase_entered_at`/`phase_exit_artifact` keys + helpers in the session store;
Phase 4 keys the `pre_tool_use` block off **persisted `phase=planning`** (set/cleared
by the brainstorming skill) and treats classification as advisory. Only
exit-condition detection remains deferred to Phase 6. Folded into: Phase 2 + Phase 4
narratives and tables, follow-up #1.

### R3 — Toggle schema/dependencies → compile-time validation

Features depend on each other (F1 and F4 both consume F5's store) but `features.yaml`
had no schema and no dependency model — disabling `services.session_memory` silently
broke an enabled `gates.search_first`. **Resolution:** `compile_features` validates a
declared key schema (unknown keys warn, wrong types fail) and a dependency table
(`gates.search_first → services.session_memory`,
`learning_extraction → services.session_memory`); unmet dependency **fails
`features sync`** with an explicit message — no silent auto-degrade. Read-time
fail-open unchanged. Folded into: cross-cutting toggles section, Phase 0 table.

### R4 — Memory data format → versioned entry schema + deterministic merge

Caps had numbers but entries had no shape and "merged at read time" had no algorithm.
**Resolution:** entry schema
`{schema_version, ts, session_id, kind: decision|blocker|pattern|phase,
summary ≤220, refs[]}`; deterministic merge (recency-first, dedup on
`(kind, normalized-summary)`, tie-break `(ts, session_id)`) producing byte-identical
digests on re-read; unknown `schema_version` skipped, not crashed. Folded into:
Phase 2 narrative and table.

### R5 — Tier-2 budget enforcement → pre_tool_use budget sidecar (HITL choice)

"Hard budgets written into the dispatch prompt" were directives an agent may ignore —
the observed 194k-token run was the advisory model failing. **Resolution (chosen over
advisory-accepted-in-writing):** the skill writes `state/budget_<session>.json` before
each Tier-2 dispatch; `pre_tool_use` counts tool calls / file reads and hard-blocks
past the limit ("summarize what you have and finish", exit 2) — the same deterministic
layer as the TDD and F4 gates. No sidecar ⇒ passthrough; corrupt sidecar ⇒ fail-open.
The prompt clause stays as graceful steering before the wall. Folded into: Phase 5
narrative, table (`pre_tool_use.py`, `test_dispatch_budget.py`), tasks.
