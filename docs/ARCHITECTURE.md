# Harness Architecture (`src/harness/`)

> Generated from a full-codebase review on 2026-06-12. ~10,000 lines of Python across 6 subsystems.

## Big Picture

The harness is a **workspace minting and orchestration tool**: it stamps an AI-agent
"operating system" (hooks, skills, agents, rules, MCP servers) into a user's repo for one of
five platforms (Claude Code, Gemini CLI, Codex, Cursor, generic), then keeps that deployment
updatable in place.

There are two **planes**, and the distinction drives almost every design decision:

1. **Tool plane** (`init/`, `update/`, `adapters/`, `domain/` compile-side) — runs on the
   developer's machine with the full `harness` package, PyYAML, Jinja2, Langfuse installed.
2. **Deployed plane** (`templates/boilerplate/` + the runtime slice) — ships *into* the user's
   repo and must run **standalone** (stdlib + whatever the minted `pyproject.toml` provides).
   Imports are flattened at mint time (`harness.runtime.X` → `X`) by `rewrite_imports`.

```
                       ┌─────────────────────────────────────────────────┐
                       │              harness-wf CLI (init/cli.py)        │
                       │  init │ update │ domain-init/refresh/compile │   │
                       │       │        │ features sync                   │
                       └──┬────┴───┬────┴──────────┬─────────────────────┘
                          │        │               │
              ┌───────────▼──┐  ┌──▼─────────┐  ┌──▼──────────┐
              │ init/        │  │ update/    │  │ domain/     │
              │ minting_     │  │ updater    │  │ seed        │
              │ engine       │  │ manifest   │  │ detect      │
              │ plugin_gen   │  │ classific. │  │ compiler    │
              │ render       │  │ conflict   │  │ model+server│──── MCP: domain_ops
              │ runtime_slice│  └──────┬─────┘  └─────────────┘
              │ features     │         │
              │ lang_aliases │   3-way merge, ownership manifest,
              │ rtk          │   journaled transactional apply
              └──────┬───────┘
                     │ mints / renders
       ┌─────────────▼───────────────────────────────────────────┐
       │ templates/boilerplate/  (DEPLOYED PLANE)                 │
       │  hooks/   prompt_classifier, pre/post_tool_use,          │
       │           session_start/end, session_memory_save         │
       │  skills/  19 SKILL.md workflows                          │
       │  agents/  6 personas (planner/implementer/debugger/…)    │
       │  rules/   packs/{common,python,golang,typescript}        │
       │  scripts/ extract_skills, session_phase, …               │
       │  src/     ← runtime slice copied+rewritten at mint       │
       └─────────────▲───────────────────────────────────────────┘
                     │ copied via RUNTIME_FILE_MAP
       ┌─────────────┴───────────────┐    ┌──────────────────────┐
       │ runtime/                    │    │ adapters/            │
       │  dispatcher (A–E routing)   │    │  base.py (ABCs)      │
       │  llm_client (CLI subproc)   │    │  claude/gemini/codex │
       │  fallback_keywords (shared) │    │  cursor/generic      │
       │  context_builder            │    │  profile.py +        │
       │  langfuse_compat/instrum.   │    │  platform_profiles   │
       └─────────────────────────────┘    │  runtime_adapter.py  │
                                          └──────────────────────┘
```

## Subsystems

### `adapters/` — platform abstraction
- **`platform_profiles.json`** is the single data source for platform facts (config dir,
  env var, tool mappings, invocation syntax, plugin support). **`profile.py`** is its typed,
  cached, validated accessor (stdlib-only by design, shippable into plugins).
- **`base.py`** declares two segregated ABCs — `RuntimeAdapter` (deployed-plane behaviours)
  and `PlatformBuilder` (mint-time behaviours) — unified by `PlatformAdapter` for the five
  concrete adapters. A `generate_core_infrastructure` → `assemble_layout` migration (S2-T3/T4)
  is mid-flight: the shim layer still exists.
- **`runtime_adapter.py`** is the *canonical, profile-driven* runtime adapter that ships into
  minted plugins (one class handles all platforms via profile flags like `generalist_remap`).
  Gemini/Codex/Cursor canonical adapters delegate `format_hook_response` to it; **Claude's
  does not** (hand-maintained copy, pinned byte-identical by `tests/unit/test_runtime_adapter.py`).
- Hook-response strategy per platform: Claude = prompt-rewrite + `additionalContext`;
  Gemini/Codex = append-only `additionalContext`; Cursor = honest no-op (`{continue: true}`,
  routing delivered via rules files + native subagents instead).

### `init/` — minting pipeline
- **`cli.py`** — argparse entry (`harness-wf`); commands: `init`, `update`, `domain-init`,
  `domain-refresh`, `domain-compile`, `features sync`. `init` orchestrates: CodeGraph index →
  mint into `.harness_tmp` → plugin generation (Claude only) → root-staging merge → smart
  merge with the existing harness → **atomic swap** (backup + move, keep last 3 backups) →
  embedded setup/validation → manifest stamping → domain seed.
- **`minting_engine.py`** — copies boilerplate, runs the **two-pass render**
  (Pass 1: placeholders + custom-delimiter Jinja `<!--$ $-->` + tool-name mapping;
  Pass 2: `@include` inlining), installs **rules packs** (stack-matched language packs into
  `<project>/.claude/rules/harness/`, with persona-inlining for non-Claude platforms),
  smart-merge helpers (`merge_markdown`, `merge_structured`, `handle_code_conflicts`).
- **`render.py`** — the single source of truth for the render transform, shared by mint and
  update so reproduced bytes match. Documents its intentional quirks (naive `.claude` replace,
  silent Jinja failure). Tool-name mappings deliberately never touch `.py` files (m3 incident).
- **`runtime_slice.py`** — `RUNTIME_FILE_MAP` (what ships into plugin `src/`),
  `rewrite_imports`, `emit_platform_adapter`, and `reproduce_runtime_file` (read-only mirror of
  the mint write path, used by update to build "theirs").
- **`features.py`** — validates/compiles operator-edited `features.yaml` → `features.json`
  (deployed hooks read only the JSON; fail-open semantics). **`lang_aliases.py`** maps
  Linguist names → pack dirs. **`rtk.py`** — optional RTK output-compression integration.

### `runtime/` — routing brain (ships in the slice)
- **`dispatcher.py`** — `OrchestratorDispatcher`: classifies each prompt into branches
  **A** (bugfix) / **B** (design) / **C** (question) / **D** (TDD edit) / **E** (chat) via an
  LLM call through the platform CLI, falling back to **`fallback_keywords.py`** (the shared
  keyword table — parity between tool plane and deployed plane is pinned by
  `test_fallback_parity.py`). `BRANCH_ROUTING` maps branch → (skill, agent).
  `evaluate_artifacts` derives phase + authorization message.
- **`llm_client.py`** — `query_llm`: subprocess to `claude`/`gemini` CLI with JSON output,
  tenacity retries, token accounting into Langfuse, `HARNESS_MOCK_LLM` test hook.
- **`context_builder.py`** — renders the `=== SYSTEM STATE ===` block (branch, phase,
  authorization, capped business digest, search-first gate status).
- **`langfuse_compat.py` / `langfuse_instrumentation.py`** — v3-style `langfuse_context`
  shim over the v4 client; defensive no-credential no-ops.

### `domain/` — project-ops manifest (the `domain` MCP)
- **`model.py`** (`OpsManifest`, stdlib-only) + **`server.py`** (FastMCP, single `domain_ops`
  pull tool) ship in the runtime slice. **`detect.py`** (Linguist API / extension fallback +
  cdxgen BOM), **`seed.py`** (`domain-init` scaffold, never clobbers), **`compiler.py`**
  (`domain-compile`: one bounded LLM call distilling reference docs → `business` section)
  stay tool-plane. This package is the cleanest in the codebase: pure functions, injected
  side effects, graceful degradation.

### `update/` — in-place update machinery
- **`classification.py`** — pure ownership map: deployed path → (class: generated /
  customizable / derived, producer: template / runtime_copy / export / emitted / verbatim,
  source). Unrecognised paths are invisible (update never touches what it can't positively own).
- **`manifest.py`** — `.harness-meta.json` bill-of-materials (normalized two-hash scheme:
  `source_hash` + `rendered_hash`) and the gzip base sidecar for customizable files.
- **`updater.py`** — verdict truth table (`we_changed × user_edited` → current / apply /
  keep-yours / conflict), transactional apply (staging copy → journaled commit →
  `recover_journal` crash recovery), B0 path migration, post-apply hooks (features recompile,
  pack mirror regen, Claude-only hook-event re-injection).
- **`conflict.py`** — diff3 via `git merge-file`, interactive K/O/D/M resolver, headless
  fail-closed.

### `templates/boilerplate/` — the deployed payload
- **hooks**: `prompt_classifier` (UserPromptSubmit → routing dispatch), `pre_tool_use`
  (security gates: `.env` access, dangerous `rm`; TDD gate; search-first gate; dispatch-budget
  backstop), `post_tool_use` (opt-in formatter), `session_start`/`session_memory_save`
  (session-memory digest/heartbeat), `session_end` (background skill-learning extraction
  with lockfile), `notify_compression`.
- **`hook_common.py`**: shared library — root/session resolution, feature-toggle reads,
  session-memory store (atomic writes, retention, capped digest), learned-skills digest.
- Platform deltas are applied at mint: event-name remap for Gemini, `${PLUGIN_ROOT}` env-var
  templating, Claude-only Stop/SessionStart injection.

## What's Right (worth protecting)

1. **The two-plane split with `rewrite_imports` + `RUNTIME_FILE_MAP`** — one source tree, one
   declarative map, reproducible deployed bytes. `reproduce_runtime_file` giving update a
   side-effect-free mirror of the mint path is the keystone of the whole update design.
2. **`update/` as a system** — ownership classification that refuses to guess, two-hash drift
   detection, journaled transactional commits with crash recovery, diff3 conflicts with stored
   bases, headless fail-closed. This is genuinely production-grade.
3. **Profile-driven platform data** (`platform_profiles.json` + `profile.py`) — platform facts
   in data, not code; validated, cached, frozen.
4. **`domain/`** — small, pure, dependency-injected, honestly documented failure modes.
5. **Shared single sources with drift tests** — `fallback_keywords.py` + parity test,
   `render.py` shared by mint/update, `runtime_adapter` byte-identity test. The team has
   clearly been burned by drift and built guards.
6. **Fail-open hook discipline** — every deployed hook is wrapped so it can never break the
   user's session; security gates fail closed where it matters (deny), telemetry fails silent.
7. **Honest platform handling** — Cursor's "we cannot inject, so we don't pretend" is the
   right call and well documented inline.

## Known Tensions / Debt (see REVIEW-harness-2026-06-12.md for the full issue list)

- `init/cli.py:main` is a 412-line god-function doing orchestration, merging and printing.
- ClaudeAdapter still hand-duplicates the canonical hook-response logic (test-pinned, but the
  delegation that gemini/codex/cursor already do is sitting right there).
- The S2-T4 adapter migration and "S2-T7 delete per-platform standalone files" steps were
  completed in spirit (the files are gone) but the back-compat shims and comments remain.
- The platform-choice digit map (`"1"→gemini …`) exists in three places.
- `.claude/harness-wf-plugin` is hardcoded in ~6 places despite `profile.domain_root_rel()`
  existing precisely to own that knowledge.
