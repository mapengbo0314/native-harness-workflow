---
title: Harness Fluidity — Single-Source Adapters & Mint-Verify
status: Proposed
date: 2026-05-29
author: harness brainstorming (Claude + Pengbo)
topic: harness-fluidity
split_out: 2026-05-30-deterministic-routing-design.md
related:
  - .claude/docs/designs/2026-05-30-deterministic-routing-design.md
  - .claude/docs/designs/2026-05-29-context-engine-proposal.md
---

# Harness Fluidity — Single-Source Adapters & Mint-Verify

> Deterministic routing was the original Slice 3 of this design; it was extracted into
> `2026-05-30-deterministic-routing-design.md` on 2026-05-30. **This document is the
> prerequisite for it** — the routing work ships its classifier into minted plugins using
> the copy mechanism established here (Slice 2), and verifies routing through the
> mint-and-verify matrix built here (Slice 1).

## Part 1: Problem Understanding

`src/harness` mints platform-specific agent plugins (Claude, Gemini, and later
Cursor/Codex/generic) from a shared boilerplate. Two problems make the code hard to trust
and hard to evolve:

1. **Adapter logic is triplicated and hand-synced.** Each platform's runtime behavior
   (`format_hook_response`, `get_subagent_text_call`, tool mappings, skill/subagent format
   strings) exists in _three_ places: the canonical `adapters/<platform>.py`, the monolith
   `runtime/platform_adapter.py`, and the standalone
   `runtime/platform_adapter_<platform>.py`. They are kept identical by hand. Nothing
   asserts they match, so they can silently drift — and tests exercise the monolith while
   production ships the standalone.

2. **There is no cross-platform "mint → verify it actually works" safety net.** Today the
   only way to know a change didn't break minting is to manually mint, check the plugin
   exists, check routing behaves, and check skills/MCPs are installed. The contract test is
   Claude-only; snapshots are uneven; routing is never asserted end-to-end after a mint.
   This is the single biggest source of fear when changing the harness.

(A third problem — non-deterministic routing — is addressed in the separate
[Deterministic Routing](2026-05-30-deterministic-routing-design.md) design.)

**Goal:** make `src/harness` fluid and trustworthy — one source of truth per concern and
an automated cross-platform mint-and-verify matrix — without a big-bang rewrite.

### Decisions locked with the user

- **Adapters → one platform abstraction (factory + interface), not codegen.** Two layers:
  (a) a **declarative JSON profile registry** (`platform_profiles.json`) holding the
  per-platform _syntax_ as a readable map (config dir, tool/event mappings, skill/subagent
  syntax, rules pointer, manifest format) **plus capability flags** — notably
  `supports_plugin` and `plugin_dir_name`; and (b) a **polymorphic `PlatformBuilder`**
  (Strategy behind the existing `get_adapter` factory) that owns _structure & process_ —
  it branches on capabilities to assemble either a **plugin stack** (when
  `supports_plugin`, emitted into a `harness-wf-plugin/` folder) or an **embedded** layout.
  (Supersedes the earlier "spec+codegen" idea — codegen can substitute syntax strings but
  cannot express structural branching like plugin-vs-embedded; see Part 3.)
- **Runtime slice ships by copy, not codegen.** The small runtime behavior that must run
  inside the plugin (`format_hook_response` + the format strings) is **copied** into the
  plugin via the existing `copy_runtime_modules` path (the same mechanism already proven
  for `dispatcher.py`), deleting the five hand-written `platform_adapter_<platform>.py`
  standalones **and** the monolith `runtime/platform_adapter.py`. (Monolith confirmed
  unused by the dispatcher; the copied canonical runtime slice replaces the standalones.)
- **Mint-verify matrix scope:** **Claude + Gemini now**, designed so adding a new platform
  is "one JSON profile block + one `PlatformBuilder` subclass."

## Part 2: Technical Plan

Two slices, ordered so the safety net exists before we refactor under it.

**Slice 1 — Mint-and-verify safety net (do first).**
A parametrized e2e matrix that, per platform, mints headlessly into a temp dir and
asserts: required artifacts exist (plugin/config, hooks, skills, MCP config,
AGENTS/orchestrator), skills+MCPs are installed, and canned routing scenarios route to the
correct skill+agent. Plus a _drift-guard_ test that captures the current adapters' runtime
output so the Slice 2 refactor is provably behavior-preserving.

**Slice 2 — One platform abstraction: JSON profile + polymorphic builder.**
Split each adapter along the two axes that genuinely differ per platform. **Syntax**
(config dir, tool/event mappings, skill & subagent invocation strings, rules pointer,
manifest format) becomes pure data in a single readable map, `platform_profiles.json`,
keyed by platform — plus capability flags (`supports_plugin`, `plugin_dir_name`).
**Structure & process** (lay out a plugin stack vs embed flat, install hooks, configure
CLI) becomes a **polymorphic `PlatformBuilder`** behind the existing `get_adapter`
factory; concrete builders branch on the profile's capabilities — e.g. `supports_plugin`
emits the plugin architecture into `harness-wf-plugin/`, otherwise the embedded layout.
The small **runtime slice** (`format_hook_response` + format strings) is **copied** into
the plugin by the same `copy_runtime_modules` path already used for `dispatcher.py`. The
monolith and the five hand-written `platform_adapter_<platform>.py` standalones are
deleted. Onboarding a new platform becomes "one JSON profile block + one builder
subclass." Codegen is **not** used — it can substitute syntax strings but cannot express
the plugin-vs-embedded structural branching (see Part 3).

**Slice 3 — Deterministic routing** → moved to
[`2026-05-30-deterministic-routing-design.md`](2026-05-30-deterministic-routing-design.md).
It depends on Slice 2's copy mechanism and Slice 1's matrix.

## Part 3: Alternatives Considered

- **Adapters: spec + codegen (render the standalone from a template).** Rejected as the
  spine: codegen substitutes per-platform _syntax strings_ fine, but the real divergence is
  _structural_ — Claude assembles a plugin stack (moves `skills/agents/hooks/scripts/src`
  into a plugin folder), Gemini embeds flat. A data-file-plus-one-template can't branch on
  "plugin vs embedded." That branching is behavior, so it belongs in a polymorphic builder,
  not a template. We keep codegen's good half — pure syntax as declarative data — in
  `platform_profiles.json`, and ship the runtime slice by copy.
- **Adapters: keep three hand-synced copies + a drift-guard test.** Rejected: preserves the
  triplication and the hand-sync burden. (We still _use_ a drift-guard test in Slice 1 —
  but only to pin status quo before deleting the copies; it is retired in the same step
  that deletes them, per S2-T7.)
- **Big-bang src/harness rewrite.** Rejected: high blast radius with no safety net. Phased
  slices, net-first.
- **Profile format: TOML vs JSON.** JSON chosen for the platform-syntax registry: one
  readable `platform_profiles.json` map (`{platform: {…syntax…, capabilities}}`) keeps the
  data centralized and easy to scan when reasoning about minting. (Scoped to the
  platform-syntax data; it does not commit the broader config to JSON.)

## Part 4: Detailed Implementation Plan

TDD throughout: each behavior gets a failing test (RED) before minimal code (GREEN), then
refactor. Tasks are bite-sized.

### Slice 1 — Mint-and-verify safety net

**`tests/e2e/_mint_helpers.py`** (new) — Rationale: one headless-mint fixture reused by all
matrix tests.

- S1-T1: Write `mint_platform(tmp_path, platform) -> Path` that runs the headless mint
  pipeline into a temp dir and returns the plugin root.

**`tests/integration/test_adapter_drift_guard.py`** (new) — Rationale: pin current runtime
behavior of all three adapter representations before Slice 2 deletes two of them.

- S1-T2 (RED→GREEN): For claude+gemini, assert `format_hook_response` and
  `get_subagent_text_call` produce identical output across `adapters/<p>.py`,
  `platform_adapter.py` (monolith), and `platform_adapter_<p>.py`. Fix any real drift found
  so the guard is green (documents the canonical behavior). **This guard is a throwaway pin
  — retired in S2-T7 alongside the files it references.**

**`tests/e2e/test_mint_and_verify_matrix.py`** (new) — Rationale: replace the manual mint
checklist with a **layered** assertion suite, parametrized over `["claude", "gemini"]`.
Verification is a ladder — existence (L1) → wiring (L2) → static validity (L3) → execution
(L4) → behavior (L5) — because each layer catches failures invisible to the one below
("the file exists" ≠ "it's wired" ≠ "it's valid" ≠ "it runs").

- S1-T3 (RED first) — **L1 existence + L2 wiring/registration**: required paths exist
  (plugin/config, hooks config, `skills/`, MCP config, AGENTS/orchestrator); AND every
  manifest reference resolves — each `hooks.json` command points to a script that exists,
  each `agents.json` entry resolves under the plugin root (catches absolute-path
  breakage), the hook **event names are the platform-correct set** (Claude
  `PreToolUse`/`PostToolUse`/`PreCompact` vs Gemini's renamed `AfterTool`/`PreCompress`),
  and `plugin.json`/`marketplace.json` carry a **substituted** name+description (catches
  the observed `"…orchestrator plugin for ."` non-substitution bug).
- S1-T4: `test_skills_and_mcp_installed` — every boilerplate skill dir is present and the
  codegraph MCP entry exists in the platform's config.
- S1-T5 — **L5 behavior (routing scenarios)**: reuse `tests/sandbox/runner.py` + the
  `tests/sandbox/scenarios/*.yaml` to assert each canned prompt routes to the expected
  skill+agent inside the minted plugin.

**`tests/sandbox/runner.py`** (modify) — Rationale: make the scenario runner importable as a
verification helper.

- S1-T6: Expose a `run_scenario(plugin_root, scenario) -> RoutingResult` entry point; no
  behavior change to the CLI path.

**`tests/e2e/test_mint_static_validity.py`** (new) — Rationale: L3 — artifacts are not just
present and wired, they are well-formed (declarative surfaces top out here; the model
reads skills/agents, so "valid + discoverable" is the right ceiling for them).

- S1-T7 — **L3 static validity & hygiene**: every JSON manifest parses; every `SKILL.md`
  and agent `.md` has required frontmatter (`name`, `description`); every hook script
  compiles (`py_compile`); the copied runtime slice has **zero `harness.*` imports**; and
  **no `__pycache__`/`.pyc`** or other build artifacts were shipped into the plugin
  (catches the observed stale cpython-311/312 bytecode under `src/`). Skill/agent text has
  tool names translated per the platform's `tool_mappings`.

**`tests/e2e/test_hook_execution_contract.py`** (new) — Rationale: L4 — hooks are the only
**executable** surface; prove they actually run, not merely exist and parse.

- S1-T8 (RED→GREEN) — **L4 hook execution contract**: for each of the 4 hooks
  (`prompt_classifier`, `pre_tool_use`, `post_tool_use`, `notify_compression`), invoke the
  script the way the platform does — via its **declared interpreter** (`uv run` /
  `python3`, read from `hooks.json`), in the minted layout with `${<PLATFORM>_PLUGIN_ROOT}`
  exported — feeding a representative event JSON on stdin. Assert the exit code (`0`, or `2`
  for an intentional deny) and that stdout is **schema-valid** for that hook's contract.
  This is the test that surfaces standalone-import breakage, a missing interpreter/dep, an
  unresolved env var, or malformed hook output as an **execution failure** rather than
  silent runtime death — and it is the regression guard for the Slice 2 copy step and the
  routing design's classifier copy.

### Slice 2 — One platform abstraction: JSON profile + polymorphic builder

**`src/harness/adapters/platform_profiles.json`** (new) — Rationale: one readable map of
per-platform _syntax_ + capabilities; the single source of truth for the data layer.

- S2-T1: Object keyed by platform id. Each entry: `config_dir`, `plugin_env_var`,
  `tool_mappings`, `event_mappings` (e.g. `PreCompact→PreCompress`, `PostToolUse→AfterTool`
  for gemini — currently hard-coded in `gemini.install_hooks`), `skill_invocation`,
  `subagent_invocation`, `subagent_text_call` (+skill variant), `manifest_format`,
  `rules_pointer_files`, and **capability flags** `supports_plugin` (bool) +
  `plugin_dir_name` (e.g. `harness-wf-plugin`). `tests/unit/test_platform_profiles.py`
  validates the schema for claude+gemini.

**`src/harness/adapters/profile.py`** (new) — Rationale: typed accessor so builders and the
runtime slice read one source.

- S2-T2 (RED→GREEN): `load_profile(platform) -> PlatformProfile` (frozen dataclass); raises
  on unknown platform / missing required keys. `tests/unit/test_profile.py`.

**`src/harness/adapters/base.py`** (modify) — Rationale: segregate the interface along the
two responsibilities the code already splits in practice (mint-time vs runtime).

- S2-T3: Split `PlatformAdapter` into `RuntimeAdapter` (stdlib-only, ships into the plugin:
  `format_hook_response`, `get_tool_mappings`, `format_skill_invocation`,
  `format_subagent_invocation`, `get_subagent_text_call`, `format_subagent_prompt`) and
  `PlatformBuilder` (mint-time structure/process: `assemble_layout`, `install_hooks`,
  `configure_cli`, `get_rules_pointer_files`, `get_agent_manifest_format`). Both read from
  the profile.

**`src/harness/adapters/<platform>.py`** (modify: claude, gemini; +codex/cursor/generic
stubs) — Rationale: concrete builders own only _structural_ logic; syntax comes from the
profile.

- S2-T4 (RED→GREEN): `ClaudeBuilder.assemble_layout` keeps today's plugin-stack assembly
  (`claude.py:48-91`) but reads `supports_plugin`/`plugin_dir_name` from the profile and
  writes `harness-wf-plugin/` (renamed from `plugin-generated/`). `GeminiBuilder` = embedded
  (no-op move, `gemini.py:61-64`). A default `EmbeddedBuilder` covers
  `supports_plugin=false`. Runtime methods move into a small per-platform `RuntimeAdapter`
  reading the profile's syntax. `tests/unit/test_builders.py`.

**`src/harness/adapters/__init__.py`** (modify) — Rationale: factory by registry, not the
current `if/elif` ladder.

- S2-T5: `get_builder(platform) -> PlatformBuilder` and `get_runtime_adapter(platform) ->
RuntimeAdapter` select via a `{platform: class}` registry, defaulting to the embedded
  builder for unknown platforms.

**`src/harness/init/minting_engine.py`** (modify, `copy_runtime_modules`) — Rationale: ship
the runtime slice by **copy** (reusing the proven dispatcher path), not codegen.

- S2-T6 (RED→GREEN): Add the stdlib-only `RuntimeAdapter` module(s) + `profile.py` +
  `platform_profiles.json` to the copied core files (`minting_engine.py:596-608`), emitting
  `platform_adapter.py` that exposes a **no-arg `get_adapter()`** — pin this symbol
  contract; the minted hook imports it at `prompt_classifier.py:181`. Keep the runtime slice
  zero-`harness.*` (the import-rewrite at `minting_engine.py:620-621` only flattens
  `harness.(runtime|init)`); widen that regex set only if a copied module must import
  another. The full S1 matrix stays green — especially the **L4 hook-execution contract
  (S1-T8)**, which is what proves the copied slice actually imports and runs in the plugin.

**DELETE** — Rationale: duplication removed at the source.

- S2-T7: Remove `runtime/platform_adapter.py` (monolith) and the five hand-written
  `runtime/platform_adapter_<platform>.py` files. **Retire the S1-T2 drift-guard in the same
  commit** — it pins exactly these files. Sequenced after S2-T8 + S1 matrix green.

**`tests/unit/test_platform_adapters.py`** (modify) — Rationale: repoint to the copied
runtime slice.

- S2-T8: Assert the copied `platform_adapter.py` exposes no-arg `get_adapter()`, has zero
  `harness.*` imports, and its `format_hook_response`/`get_subagent_text_call` output equals
  the S1-T2 canonical; drop monolith/standalone import assertions.

### Sequencing constraints

- Slice 1 before Slice 2 (safety net before refactor).
- S2-T1/T2/T3 (profile + accessor + interface split) before S2-T4/T5/T6 (builders, factory,
  and the copy step all consume them).
- S2-T7 (delete monolith + standalones, retire S1-T2 drift-guard) only after S2-T8 (tests
  repointed to the copied runtime slice) and S1 matrix green.
- The Deterministic Routing design's classifier-copy (its R-T7) depends on S2-T6 landing
  first.

## Part 5: Success Criteria & Mint-Test Strategy

The point of Slice 1 is to replace "fear + manual checklist" with a measurable, repeatable
verdict. This section defines what "minting works" means and how we test minting itself.

### What we measure (Definition of Done)

A slice is done only when all of these are **green in CI**, for **every platform in the
registry** (claude + gemini now):

Ordered by the verification ladder (L1→L5); a slice ships only when every row is green:

| Layer | Signal                | Assertion                                                                                                                                                                    | Why it matters                                          |
| ----- | --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| L1    | Artifacts exist       | every required path exists post-mint (S1-T3)                                                                                                                                 | mint produced a usable plugin                           |
| L2    | Wiring / registration | every `hooks.json` command → existing script; every `agents.json` path resolves under plugin root; platform-correct event names; `plugin.json` name+desc substituted (S1-T3) | the plugin is actually wired, not just populated        |
| L2    | Skills + MCP          | all boilerplate skills present; codegraph MCP entry written (S1-T4)                                                                                                          | skills/tools are reachable                              |
| L3    | Static validity       | all JSON parses; every `SKILL.md`/agent `.md` has `name`+`description` frontmatter; every hook script compiles (S1-T7)                                                       | malformed declarative surfaces fail at mint, not at use |
| L3    | Hygiene               | **no `__pycache__`/`.pyc`** or build artifacts shipped; copied runtime slice has zero `harness.*` imports (S1-T7)                                                            | catches the observed stale cpython bytecode in `src/`   |
| L4    | Hook execution        | each of the 4 hooks, run via its declared interpreter with a canned stdin event, exits `0`/`2` and emits schema-valid stdout (S1-T8)                                         | hooks actually RUN — the only executable surface        |
| L4    | Standalone invariant  | minted runtime slice imports with **no** `harness` on `sys.path`; `get_adapter()` no-arg returns the right platform                                                          | the plugin won't die at import in a user env            |
| L5    | Routing scenarios     | **100%** of `tests/sandbox/scenarios/*.yaml` route to the expected skill+agent inside the minted plugin (S1-T5)                                                              | the plugin behaves, not just exists                     |
| —     | Layout-by-capability  | `supports_plugin=true` → `harness-wf-plugin/` with expected subdirs; `false` → embedded layout                                                                               | the builder honored the profile                         |
| —     | Syntax applied        | tool names translated per `tool_mappings`; `event_mappings` applied (gemini hooks.json has `PreCompress`/`AfterTool`); correct rules pointer (`CLAUDE.md`/`GEMINI.md`)       | the profile data actually took effect                   |
| —     | Behavior preservation | copied runtime slice output == S1-T2 canonical (before delete); drift-guard green                                                                                            | Slice 2 changed nothing observable                      |
| —     | Profile schema        | `platform_profiles.json` validates for every registered platform (S2-T1)                                                                                                     | bad data fails fast, at mint, not at runtime            |

### How we mint-test (the strategy)

- **Headless mint into `tmp_path`** via the S1-T1 helper — no global state, no real CLI
  side effects (mock or assert-on-config for `configure_cli`).
- **Data-driven, not hardcoded.** Structural + syntax assertions read their expectations
  **from the profile**, so a new platform's JSON block automatically extends test coverage
  — adding a platform should not require writing a new bespoke test, only the profile +
  builder. Parametrize over `get_registry().keys()`.
- **Capability-branched layout checks.** Assert plugin-stack shape only when
  `supports_plugin`; assert embedded shape otherwise. This is the test analog of the
  builder's own branch, so the two can't silently disagree.
- **Idempotency.** Mint twice into the same dir → stable, non-corrupting result (no doubled
  dirs, no re-wrapped `harness-wf-plugin/harness-wf-plugin/`).
- **Negative / contract test for the standalone invariant.** Import the copied runtime
  slice in a subprocess with `harness` removed from `sys.path`; it must import and
  `get_adapter()` (no-arg) must return the platform — this is the failure mode that kills
  real minted plugins (`prompt_classifier.py:181`).
- **MCP wiring.** Assert the `codegraph` entry lands in the platform's config (claude vs
  gemini CLI syntax differs); mock the CLI call and assert the command, or assert the
  written config file.

### How we quantify "testing success"

- **Mint coverage = profile fields asserted / total profile fields.** A meta-test fails if
  any `platform_profiles.json` key is never asserted by the matrix — this keeps test
  coverage tracking the data as platforms grow. Target **100%**.
- **Capability coverage** = each capability flag exercised in both states across the
  registry (some platform with `supports_plugin=true`, some with `false`).
- **Routing scenario pass rate = 100%** (a single failure blocks the slice).
- **One command reproduces the verdict:** `pytest tests/e2e -m mint_matrix` (and the
  drift-guard/contract tests) — the CI gate that replaces the manual checklist.

## Part 6: Adversary Notes (adapter/mint-relevant)

Routing-specific defects (former D3–D9, C1, C2, A1–A5, A9, A10) moved with the
[Deterministic Routing](2026-05-30-deterministic-routing-design.md) design. Claims verified
against source 2026-05-29, re-checked 2026-05-30.

**D1 — The deployed `platform_adapter.py` is a LIVE runtime import (was mis-framed as
"unused").** The minted hook does `from platform_adapter import get_adapter`
(`prompt_classifier.py:181`) then `adapter.format_hook_response(...)`; minting copies a
per-platform source to `platform_adapter.py` (`minting_engine.py:603`, default
`platform_adapter_generic.py`), and tests pin the import string
(`tests/unit/test_platform_adapters.py:415-416`). The **monolith** `runtime/platform_adapter.py`
is dispatcher-unused, but the deployed copy is not. **Addressed:** S2-T6 keeps emitting
`platform_adapter.py` and **pins the no-arg `get_adapter()` symbol contract**.

**D2 — Drift-guard references files the refactor deletes.** S1-T2 asserts equality across
`adapters/<p>.py`, the monolith, and `platform_adapter_<p>.py`; S2-T7 deletes the latter
two. **Addressed:** S1-T2 is explicitly a throwaway pin, retired in the same commit as
S2-T7 (stated in both tasks).

**Undocumented assumptions (adapter/mint):**

- A6. "The monolith is fully unused." The deployed `platform_adapter.py` import is live and
  pinned by tests (D1) — only the monolith file is dispatcher-unused.
- A7. "The drift-guard is a permanent backstop." Its inputs are deleted by S2-T7; it must be
  retired in lockstep (D2).
- ~~A8 (codegen byte-determinism)~~ — **obsolete**: codegen was dropped in favor of copy +
  JSON profile, so there is no rendered-module golden-output to stabilize.

#### Overall Verdict (fluidity scope)

Low-risk as specified: the copy mechanism already exists for the dispatcher, the
`get_adapter()` contract is pinned, and the drift-guard's retirement is sequenced. The
remaining risk lived in routing and now travels with that design.
