# Phase 6a — Session Identity Repair — Progress

_Design: [2026-06-11-sticky-phase-state-machine-design.md](2026-06-11-sticky-phase-state-machine-design.md)
(Sections 0–3 HITL-approved; Tier-1 adversary review complete — M1/M2 folded; scope: fix-only 6a)_
_TDD mandatory throughout. Groups are dependency-ordered._

**Status: implementation COMPLETE (commits f0e0ac9, 8e4ced2, 3496d97). Live delivery + manual smokes pending below.**

## Group 1 — Stable session identity (+ /clear semantics)

- [x] Failing test: `get_session_id(input_json)` resolution order — `HARNESS_SESSION_ID` override → payload `session_id` → `CLAUDE_SESSION_ID`/`GEMINI_SESSION_ID` → pointer file → ppid (M1 order) (`tests/hooks/test_session_identity.py`)
- [x] Implement payload-aware `get_session_id` + `publish_session_pointer` (atomic tmp+rename, fail-open) in `hooks/hook_common.py`
- [x] Failing test: /clear simulation — two hook invocations with different payload ids never share a store; pointer overwritten by the newer session; pointer file exempt from pruning (m2)
- [x] Failing test: hooks thread their stdin payload + publish pointer (`pre_tool_use.py` — also hoist session_id/plugin_root resolution to ONCE before the gate chain; `prompt_classifier.py` — also unify on `resolve_plugin_root()` (review #7); `session_memory_save.py`; `session_start.py`; `session_end.py`)
- [x] Implement payload threading + pointer publish across the five hooks
- [x] Failing test: `session_phase.py --session` flag wins over pointer; pointer fallback when absent; legacy env/ppid last
- [x] Implement `--session` global flag; new `arm-budget`/`disarm-budget` subcommands (replaces SKILL.md heredocs — review #4)
- [x] Failing test (regression for the live-broken loop): hook engages search-first gate from payload id; `set-research-done --session <same id>` releases it (`tests/hooks/test_search_first_gate.py`); budget wall binds via `arm-budget --session <hook id>` (`tests/hooks/test_dispatch_budget.py`)
- [x] Failing test: SYSTEM STATE carries `Session: <id>` line (`tests/unit/test_context_builder.py`); implement in `runtime/context_builder.py` + classifier inline fallback
- [x] Update skill texts: `adversary-pipeline` (heredocs → arm/disarm-budget --session), `harness-brainstorming-plans` + `search-first` (pass --session; fix "optional adversarial review" contradiction — review #3); update contract tests (`tests/unit/test_adversary_pipeline.py`)

## Group 2 — Stale-state expiry completion

- [x] Failing test: old `tdd_*.json` pruned by mtime, fresh kept (review #6)
- [x] Implement in `prune_old_session_files` (`hooks/hook_common.py`)

## Group 3 — Fallback-keyword unification (review #1)

- [x] Failing test: shared table module exists with bias-to-D verbs in D, bare `'which'` in C (review #2), no dead `'fix the'` in D (review #9), precedence documented (`tests/unit/test_fallback_parity.py`)
- [x] Create `src/harness/runtime/fallback_keywords.py`; register in `src/harness/init/runtime_slice.py`
- [x] Failing test: `keyword_fast_path(prompt)` extracted from `classify_intent` (M2), consumes the table
- [x] Implement extraction in `runtime/dispatcher.py`
- [x] Failing test: parity corpus (≥20 prompts, A–E incl. precedence cases) classifies identically through `keyword_fast_path` and `fallback_classify`
- [x] Implement table consumption in `prompt_classifier.py` (inline copy only as import-failure fallback); re-point existing assertions (`tests/unit/test_dispatcher.py`, `tests/unit/test_fallback_classify.py`)

## Hardening (same files, same commits)

- [x] Failing test: atomic budget-sidecar write + check-before-write — blocked calls don't consume budget (review #5) (`tests/hooks/test_dispatch_budget.py`)
- [x] Failing test: `glob.escape` on topic in `check_risk_report.py` — bracketed design-doc name matches (review #8) (`tests/unit/test_adversary_pipeline.py`)
- [x] Refactor: shared `_deny(msg, is_gemini)` helper replacing the five block-and-exit stanzas in `pre_tool_use.py` (suite stays green — pure refactor under existing e2e tests)

## Post-merge / live delivery

- [ ] `harness-wf update` into this repo's live plugin
- [ ] Manual smoke 1: log payload session id, `/clear`, log again — confirm it changes
- [ ] Manual smoke 2 (risk-report M3): `arm-budget --max-tool-calls 2`, dispatch a trivial subagent, confirm its third call blocks
- [x] Suite + integration green — 1358 passed / 34 skipped / 3 xfailed (+106) per `domain_ops("test")`
