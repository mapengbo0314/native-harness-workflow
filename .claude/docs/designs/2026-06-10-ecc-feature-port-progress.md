# ECC Feature Port — Progress

_Design: [2026-06-10-ecc-feature-port-design.md](2026-06-10-ecc-feature-port-design.md)
(revised per Section 4 adversarial review — C1–C4, M1–M6, m1–m4; amended per Section 5
second-round review — R1–R5)_
_Phases are dependency-ordered and independently shippable. TDD mandatory throughout._

## Phase 0 — Feature-Toggle Substrate (two-file: operator YAML → compiled JSON)

- [x] Failing test: `feature_enabled` returns True with no features file (`tests/hooks/test_feature_toggles.py`) — fc5c9d9
- [x] Implement `load_features()` + `feature_enabled()` in `hooks/hook_common.py` (reads compiled JSON) — fc5c9d9, default-param fix 57deba5
- [x] Failing test: disabled key returns False; implement dotted-path traversal — fc5c9d9
- [x] Failing test: YAML→JSON compile parity (`tests/unit/test_features_loader.py`); implement `compile_features` in `src/harness/init/features.py` — fc5c9d9
- [x] Failing test (R3): unknown key warns, wrong type fails, enabled feature with disabled dependency fails compile (named dependency in message); implement schema + dependency table in `compile_features` — fc5c9d9 (+ non-dict-root guard 57deba5)
- [x] Failing test: `harness-wf features sync` subcommand + auto-sync on refresh (`tests/unit/test_cli_features_sync.py`); implement in `init/cli.py` — fc5c9d9/57deba5 (init/mint + update-path auto-sync → Task 0b)
- [x] Failing test: staleness warning when YAML newer than JSON; implement mtime guard (fn in `hook_common.py`, injection in `prompt_classifier.py`) — bdf8c13, utime-pinned tests 06d078e
- [x] Failing test: `features.yaml` ⇒ `customizable`, `features.json` ⇒ `generated`/emitted (`tests/unit/test_update_classification.py`); implement in `update/classification.py` — bdf8c13
- [x] Failing test (m3): `features.yaml` survives re-mint with operator values winning; `features.json` regenerated post-merge (not merged) — bdf8c13/06d078e; keys disjoint from codex tool-mapping vocabulary (moved to `test_features_loader.py`)
- [x] Author `templates/boilerplate/features.yaml` template + add new keys to `harness_features_tree.md` — bdf8c13
- [x] Full suite green (1070 passed/34 skipped/3 xfailed); Phase 0 = fc5c9d9, 57deba5, bdf8c13, 06d078e — two-stage reviewed, approved
- [x] Carry-over → Phase 1: `harness-wf update` path does not recompile features.json post-apply (staleness warning covers advisorily); fold into updater work — resolved by Phase 1 R1: `_post_apply_hooks` (`update/updater.py`) recompiles `features.json` after `apply_update` — 1b commits

## Phase 1 — F3 Stack-Aware Rules Packs

- [x] Failing test: language alias map (`Go`→`golang`, cdxgen framework names ignored) (`tests/unit/test_rules_packs.py`); implement `src/harness/init/lang_aliases.py` — 2382f42
- [x] Failing test: Python-only repo gets `common`+`python` only; toggle off ⇒ no packs — 2382f42
- [x] Implement pack-pruning function; install into `.claude/rules/harness/` (namespaced; stale-install prune scoped to known pack dirs, user content spared) — 2382f42 + fixes 55a93a1
- [x] Failing test: pruning + namespacing in mint flow; wire into `mint_workspace` + re-mint + refresh — wiring commit + d82ca8e integrity tests (persona inlining on non-Claude platforms → Task 1c with content)
- [x] Failing test (C4): pruned packs never re-proposed by update (`tests/unit/test_update_updater.py`); stack filter persisted in `render_context.rules_packs`, `plan_update` filters producers; empty/unknown selection fails open — 1b commits + b905c26
- [x] Failing test (R1): `.claude/rules/harness/` is a generated mirror — `_post_apply_hooks` regenerates mirror + recompiles features.json after `apply_update` (behavioral test: new content delivered, operator edits inside mirror overwritten) — 1b commits
- [x] Failing test: `domain-refresh` re-syncs packs AND rewrites the manifest's `rules_packs` filter (stale-filter gap closed); implement in `init/cli.py` (`_compute_rules_packs_rc` single source) — 1b commits
- [x] Author pack content with `paths` frontmatter (lazy-load) — curated from ECC@c888d2b: `common/` 4.3KB un-scoped (3 files), `python/` 3.8KB, `typescript/` 4.1KB, `golang/` 2.7KB; provenance headers; non-Claude persona inlining w/ marker idempotency + orphan healing — 1c commits
- [x] Update `tests/integration/test_template_integrity.py` (size budgets, frontmatter, provenance, no placeholders); suite green (1124/34/3); Phase 1 complete — two-stage reviewed, approved

## Phase 2 — F5 Session Memory

- [x] Failing test (R4): write→read round-trip with entry schema `{schema_version, ts, session_id, kind, summary ≤220, refs[]}` (`tests/hooks/test_session_memory.py`)
- [x] Implement `hooks/session_memory_save.py` — Stop-event (per-response, idempotent) write to `state/session_memory_<session>.json`
- [x] Failing test (M6): two concurrent sessions don't clobber; per-session file naming
- [x] Failing test (R4): deterministic merge — recency-first, dedup on `(kind, normalized-summary)`, byte-identical digest on re-read; unknown schema_version skipped not crashed; implement in `hook_common.py`
- [x] Failing test: caps (≤8 KB, ≤6 entries, 220-char summaries) + 30-day retention; implement helpers in `hook_common.py`
- [x] Failing test (R2): phase keys (`phase`, `phase_entered_at`, `phase_exit_artifact`) round-trip; implement `set_phase`/`get_phase`/`clear_phase` in `hook_common.py`
- [x] Failing test: SessionStart digest injection (merge-at-read); implement `hooks/session_start.py` with `HARNESS_SESSION_CONTEXT=off` opt-out
- [x] Failing test: wiring (`tests/integration/test_claude_plugin_contract.py`); register Stop/PreCompact/SessionStart in `hooks.json` + `adapters/claude.py` (gemini only after event verification — M4)
- [x] Failing test: toggle-off ⇒ no-op; wire `services.session_memory` gate

Phase 2 has passed `harness-subagent-driven-development` workflow (Spec Compliance: ✅ Compliant, Code Quality: ✅ Approved). Phase 2 is **complete**.

## Phase 3 — F1 Continuous Learning

- [x] Failing test (C2): `HARNESS_INTERNAL_LLM_CALL=1` short-circuits hook; lockfile exclusion (`tests/hooks/test_session_end_learning.py`)
- [x] Implement guards in new `hooks/session_end.py` (SessionEnd event — C1, not Stop)
- [x] Failing test: transcript→SKILL.md shape, slug/confidence/tag, out-of-repo store path `~/.local/share/harness-wf/projects/<hash>/learned/` (`tests/unit/test_skill_extraction.py`, LLM mocked)
- [x] Implement `scripts/extract_skills.py`
- [x] Failing test: dedup + min-session threshold (≥10 turns) + fail-open on LLM error/timeout
- [x] Wire detached spawn behind `hooks.session_end.learning_extraction` gate; register SessionEnd in `hooks.json`
- [x] Failing test: SessionStart injects ≤6 learned summaries; edit `hooks/session_start.py`
- [x] Author `skills/continuous-learning/SKILL.md` (`/learn`); register in `skills.json`

Phase 3 has passed `harness-subagent-driven-development` workflow (Spec Compliance: ✅ Compliant, Code Quality: ✅ Approved). Phase 3 is **complete**.

## Phase 4 — F4 Search-First Gate (+ proportionality guards)

- [x] Failing test: Branch B + no `research_done` ⇒ gate line in SYSTEM STATE (`tests/unit/test_context_builder.py`)
- [x] Implement gate line in `runtime/context_builder.py` (m1 — NOT prompt_classifier; + its inline fallback) — `search_first_pending` kwarg, default off for legacy callers; classifier threads it via branch-scoped `_search_first_pending` (hot-path: non-B skips session I/O); inline fallback carries the same line (`tests/unit/test_prompt_classifier_search_gate.py`)
- [x] Failing test (M1, R2): source write blocked while persisted `phase=planning` without flag; allowed with flag; classification flip mid-phase does NOT drop the gate; no persisted phase ⇒ passthrough; no TDD-gate interference (`tests/hooks/test_search_first_gate.py`, `tests/unit/test_pre_tool_use_tdd.py`)
- [x] Implement enforcement in `hooks/pre_tool_use.py` via `get_phase` (NOT per-prompt branch) behind `pipeline.dispatcher.gates.search_first` — `_check_search_first`, fail-open, runs before the TDD check; e2e exit-2 + gemini deny-JSON covered
- [x] Failing test (R2): brainstorming skill sets `phase=planning` + `phase_entered_at` on entry, clears with `phase_exit_artifact` on sign-off; implement in `skills/harness-brainstorming-plans/SKILL.md` + contract test — phase mutations via new `scripts/session_phase.py` (set-phase/clear-phase/set-research-done CLI; skills are markdown and need a deterministic invocable — small addition beyond the design's file list); `research_done` helpers + `research` entry kind in `hook_common.py`
- [x] Failing test: ambiguous implement-style prompts ⇒ Branch D, clear design work ⇒ B (`tests/unit/test_dispatcher.py`, `tests/unit/test_fallback_classify.py`) — re-categorised the implement-style prompts that previously asserted B
- [x] Implement bias-to-D rule in `classify_intent` prompt (`runtime/dispatcher.py`) + `prompt_classifier` fallback; D pre-flight asks 1–2 clarifying questions instead of escalating to B — BRANCHES menu descriptions updated too (B no longer claims implement-verbs)
- [x] Failing test: toggle off ⇒ passthrough; waiver path sets `research_done`; wire toggle — covered in `test_search_first_gate.py` (toggle-off predicate + steering) and the live-gate release loop via the script
- [x] Author `skills/search-first/SKILL.md` — step 1 proportionality waiver, then Adopt/Extend/Compose/Build matrix, then **post-research depth checkpoint** (HITL `AskUserQuestion`: quick implementation w/ findings attached + clear `phase`, vs full planning pipeline; matrix outcome = recommended default); register in `skills.json` + contract test for checkpoint text

Phase 4 suite: 1218 passed / 34 skipped / 3 xfailed (+43 tests). Phase 4 is **complete**.

## Phase 5 — F2 Adversary Pipeline (tiered + budgeted)

- [x] Failing test: staleness checker — report exists + newer than design doc; toggle-off ⇒ pass (`tests/unit/test_adversary_pipeline.py`) — 97c7d9a; topic matching is date-prefix tolerant, newest-report-wins, bad-input exit 2
- [x] Implement `scripts/check_risk_report.py` (no dispatcher gate — C3: insertion point doesn't exist) — 97c7d9a
- [x] Failing test (R5): budget sidecar `state/budget_<session>.json` — counter increments per tool call, block past limit with summarize-and-finish message, no sidecar ⇒ passthrough, corrupt sidecar ⇒ fail-open, per-session isolation (`tests/hooks/test_dispatch_budget.py`) — 793b092 (16 tests, incl. e2e exit-2 + gemini deny-JSON)
- [x] Implement budget backstop in `hooks/pre_tool_use.py` (R5 — same deterministic layer as TDD/F4 gates) — 793b092; spec gap closed: `prune_old_session_files` now also reaps stale `budget_*.json` by mtime (design said "pruned by the Phase 2 retention helper" but the helper only globbed `session_memory_*`)
- [x] Author `skills/adversary-pipeline/SKILL.md` — Tier 1: inline council-style role lenses (default, no subagents); Tier 2: Attacker→Defender→Auditor general-purpose dispatches, **skill writes the budget sidecar before each dispatch (R5)** (≤30 tool calls, ≤12 files, smaller model for Attacker/Defender, degrade-gracefully clause as steering before the enforced wall); council role-lens + GAN prompt-defense preamble; re-scope `agents/adversary.md` as Auditor — dfd4eb7; sidecar armed/disarmed via `hook_common.get_session_id()` so writer and enforcer resolve identically
- [x] Add skill-text gate to `harness-brainstorming-plans` + `harness-requesting-code-review` SKILL.md behind `pipeline.dispatcher.gates.adversary_exit` — dfd4eb7; brainstorming Part 5 re-routed through the pipeline (was: bare dispatch of the inert plugin adversary agent)
- [x] Register skill; update `tests/integration/test_claude_plugin_contract.py` — dfd4eb7 (minted-plugin assertions: skill + script present, gate text in both sign-off skills)

Phase 5 suite: 1252 passed / 34 skipped / 3 xfailed (+34 tests). Phase 5 is **complete**.

Pre-Phase-5 housekeeping (same session): two stale `tests/hooks` classifier contract tests still asserted pre-Phase-4 fallback behavior (`implement ⇒ B`) against the live deployed plugin — aligned with bias-to-D (4f5ddd6).

## Phase 6 — Sticky Phase State Machine → design pass COMPLETE, scope narrowed to 6a

- [x] Run its own design pass (Sections 0–4) — done 2026-06-11: [2026-06-11-sticky-phase-state-machine-design.md](2026-06-11-sticky-phase-state-machine-design.md), Tier-1 adversary-reviewed (first production use of the Phase 5 skill), commit 6ed19f3
- **Scope decision (HITL):** fix-only **Phase 6a** — stable session identity (the design pass uncovered that skill-invoked scripts write to dead session stores, leaving the Phase 4 gate and Phase 5 budget wall live-inert; observed id drift `73171`→`80226`→`80490`), /clear-means-fresh, `tdd_*` prune gap, fallback-keyword unification. Tasks: [2026-06-11-sticky-phase-state-machine-progress.md](2026-06-11-sticky-phase-state-machine-progress.md)
- Sticky-mode machinery (ledger merge, artifact exit detection, classifier shrink, misroute suppression) **deferred to Phase 6b** — re-open if within-conversation misrouting keeps hurting after the repair
- Persistence half already shipped per R2: phase keys + helpers (Phase 2), brainstorming-skill set/clear (Phase 4)

## Phase 2 Implementation Summary

**Summary:** Addressed code reviewer feedback. Fixed the reference truncation bug in `build_session_digest` by joining all references. Fixed the corrupt file disk leak in `prune_old_session_files` by ensuring files that throw exceptions during timestamp parsing are pruned. Rewrote `test_digest_8kb_cap` to correctly trigger the 8KB limit by utilizing the uncapped `refs` array.
**Verified:** `tests/hooks/test_session_memory.py` passes successfully, proving all fixes. SDD workflow complete.

## Phase 3 Implementation Summary

**Summary:** Implemented Phase 3 F1 Continuous Learning skill extraction and injection. Following an Adversary agent audit, fixed 6 critical vulnerabilities across prompt classification, lockfile state management, frontmatter parsing, and debugging log visibility:
1. **Catastrophic Infinite Recursion Loop**: Added an early recursion check in `prompt_classifier.py` (`HARNESS_INTERNAL_LLM_CALL=1` exits before any LLM call) and verified with integration tests.
2. **Atomic Lockfile TOCTOU & Expirable Lockfile**: Implemented atomic lockfile creation in `session_end.py` with `os.O_CREAT | os.O_EXCL`, and robust mtime (5 minutes) and PID liveness recovery checks (`os.kill(pid, 0)`).
3. **Dead PID Remediation**: Implemented `pid=` lockfile initialization, capturing and updating with the active background `proc.pid` after spawn.
4. **Robust Frontmatter & Comment Parsing**: Developed a resilient frontmatter split/comment/quote-stripping parser in `hook_common.py` (`build_learned_skills_digest`) and `extract_skills.py` (`parse_frontmatter`) that handles inline comments (`#`) and colons seamlessly.
5. **Hook Failures Visibility**: Redirected background `extract_skills.py` stdout/stderr to `.claude/state/learning_extraction.log` (or `.gemini/state/`) for debuggability.
6. **Test Isolation**: Refactored the `tests/hooks/test_session_end_learning.py` test suite to use isolated temporary directories (`plugin_root` tmp fixture) to prevent template state pollution.
**Verified:** Successfully ran and passed all 1200+ tests, including specific newly-added cases for prompt recursion, stale lockfile recovery (mtime & dead PID), live PID locking, and robust comment/quote frontmatter parsing.
**NextSteps:** Proceed to Phase 4.

## Phase 0–3 Hardening (2026-06-11) — both-planes audit

Audit of Phases 0–3 against the live deployed plugin exposed six cross-plane defects; all fixed TDD-first (+10 tests, suite 1175/34/3):

1. **Update plane dropped Claude-only hook events**: `_produce_theirs` renders `hooks.json` from the shared boilerplate (no `Stop`/`SessionStart` — adapter injects those at mint only), so any update silently unwired session memory. Fixed: `_post_apply_hooks` step 3 re-injects via the platform adapter (`tests/unit/test_update_updater.py`).
2. **`run_domain_refresh_with_sync` used the project root as plugin root** (`cli.py`): features compile and pack re-sync were silent no-ops on standard layouts — only the manifest filter rewrite worked. Existing mock tests enshrined the bug (`assert_called_once_with(Path(tmp_path))`). Fixed + assertions corrected (`tests/unit/test_cli_features_sync.py`).
3. **`_migrate_b0_paths` migrated the generated pack mirror as legacy B0 content**: every update moved `<project>/.claude/rules/harness/` into the plugin (permanent `removed-upstream` orphans), deleted the mirror, and post-apply regenerated it — an infinite loop. Fixed: mirror subtree exempt from migration and from the legacy-cleanup rmtree (`tests/unit/test_update_updater.py`).
4. **Emitted `features.json` aborted `apply_update`** ("cannot reproduce ... producer 'emitted'") once manifest-owned. Fixed: skipped in `_resolve_into_staging`; `_post_apply_hooks` recompiles it post-commit (`tests/unit/test_update_updater.py`).
5. **Mint plane shipped plugins without the toggle surface**: `assemble_layout` payload_files omitted `features.yaml`/`features.json` — stranded at the harness root on every fresh mint. Fixed (`tests/unit/test_builders.py`).
6. **Mint permanently pruned all language packs**: `install_rules_packs` ran during mint with stack unknown (domain seed runs post-mint) ⇒ matched=∅ ⇒ language packs pruned from the deployed plugin at birth, unrecoverable by refresh. Fixed two-sided: unknown stack fails open (no prune — mirrors `_compute_rules_packs_rc`'s `selected: None` semantics; known-stack-no-match still prunes), and `_post_mint_domain_init` re-syncs packs after the seed on claude (`tests/unit/test_rules_packs.py`).

Also: stale `uv tool` install of `harness-wf` (Jun 9 snapshot) shadowed the editable install and produced blind update plans — reinstalled from source; keep it current when the lifecycle code changes. Live plugin updated through the fixed pipeline end-to-end (`update --check` converges to zero actionable verdicts; mint smoke-tested in a temp project with all Phase 0–3 artifacts asserted).