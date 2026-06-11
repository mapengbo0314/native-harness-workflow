# ECC Feature Port — Progress

*Design: [2026-06-10-ecc-feature-port-design.md](2026-06-10-ecc-feature-port-design.md)
(revised per Section 4 adversarial review — C1–C4, M1–M6, m1–m4; amended per Section 5
second-round review — R1–R5)*
*Phases are dependency-ordered and independently shippable. TDD mandatory throughout.*

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
- [ ] Carry-over → Phase 1: `harness-wf update` path does not recompile features.json post-apply (staleness warning covers advisorily); fold into updater work

## Phase 1 — F3 Stack-Aware Rules Packs
- [ ] Failing test: language alias map (`Go`→`golang`, cdxgen framework names ignored) (`tests/unit/test_rules_packs.py`); implement `src/harness/init/lang_aliases.py`
- [ ] Failing test: Python-only repo gets `common`+`python` only; toggle off ⇒ no packs
- [ ] Implement pack-pruning function; install into `.claude/rules/harness/` (namespaced)
- [ ] Failing test: pruning + namespacing in mint flow (`tests/unit/test_minting_engine.py`); wire into `mint_workspace` (+ persona inlining on non-Claude platforms)
- [ ] Failing test (C4): pruned packs never re-proposed by update (`tests/unit/test_update_updater.py`); persist stack filter in manifest `render_context` + teach `enumerate_source_producers`/`compute_verdicts`
- [ ] Failing test (R1): `.claude/rules/harness/` is a generated mirror — pack content updates in the template tree reach the deployed mirror on `harness-wf update`; operator edits inside the mirror overwritten; record install target in `manifest.py` `render_context` + regenerate step in `updater.py`
- [ ] Failing test: `domain-refresh` re-syncs packs; implement in `init/cli.py`
- [ ] Author pack content with `paths` frontmatter (lazy-load) — `common/` (≤6 KB, un-scoped), `python/`, `typescript/`, `golang/`
- [ ] Update `tests/integration/test_template_integrity.py`; suite green; commit

## Phase 2 — F5 Session Memory
- [ ] Failing test (R4): write→read round-trip with entry schema `{schema_version, ts, session_id, kind, summary ≤220, refs[]}` (`tests/hooks/test_session_memory.py`)
- [ ] Implement `hooks/session_memory_save.py` — Stop-event (per-response, idempotent) write to `state/session_memory_<session>.json`
- [ ] Failing test (M6): two concurrent sessions don't clobber; per-session file naming
- [ ] Failing test (R4): deterministic merge — recency-first, dedup on `(kind, normalized-summary)`, byte-identical digest on re-read; unknown schema_version skipped not crashed; implement in `hook_common.py`
- [ ] Failing test: caps (≤8 KB, ≤6 entries, 220-char summaries) + 30-day retention; implement helpers in `hook_common.py`
- [ ] Failing test (R2): phase keys (`phase`, `phase_entered_at`, `phase_exit_artifact`) round-trip; implement `set_phase`/`get_phase`/`clear_phase` in `hook_common.py`
- [ ] Failing test: SessionStart digest injection (merge-at-read); implement `hooks/session_start.py` with `HARNESS_SESSION_CONTEXT=off` opt-out
- [ ] Failing test: wiring (`tests/integration/test_claude_plugin_contract.py`); register Stop/PreCompact/SessionStart in `hooks.json` + `adapters/claude.py` (gemini only after event verification — M4)
- [ ] Failing test: toggle-off ⇒ no-op; wire `services.session_memory` gate
- [ ] Suite green; commit

## Phase 3 — F1 Continuous Learning
- [ ] Failing test (C2): `HARNESS_INTERNAL_LLM_CALL=1` short-circuits hook; lockfile exclusion (`tests/hooks/test_session_end_learning.py`)
- [ ] Implement guards in new `hooks/session_end.py` (SessionEnd event — C1, not Stop)
- [ ] Failing test: transcript→SKILL.md shape, slug/confidence/tag, out-of-repo store path `~/.local/share/harness-wf/projects/<hash>/learned/` (`tests/unit/test_skill_extraction.py`, LLM mocked)
- [ ] Implement `scripts/extract_skills.py`
- [ ] Failing test: dedup + min-session threshold (≥10 turns) + fail-open on LLM error/timeout
- [ ] Wire detached spawn behind `hooks.session_end.learning_extraction` gate; register SessionEnd in `hooks.json`
- [ ] Failing test: SessionStart injects ≤6 learned summaries; edit `hooks/session_start.py`
- [ ] Author `skills/continuous-learning/SKILL.md` (`/learn`); register in `skills.json`
- [ ] Suite green; commit

## Phase 4 — F4 Search-First Gate (+ proportionality guards)
- [ ] Failing test: Branch B + no `research_done` ⇒ gate line in SYSTEM STATE (`tests/unit/test_context_builder.py`)
- [ ] Implement gate line in `runtime/context_builder.py` (m1 — NOT prompt_classifier; + its inline fallback)
- [ ] Failing test (M1, R2): source write blocked while persisted `phase=planning` without flag; allowed with flag; classification flip mid-phase does NOT drop the gate; no persisted phase ⇒ passthrough; no TDD-gate interference (`tests/hooks/test_search_first_gate.py`, `tests/unit/test_pre_tool_use_tdd.py`)
- [ ] Implement enforcement in `hooks/pre_tool_use.py` via `get_phase` (NOT per-prompt branch) behind `pipeline.dispatcher.gates.search_first`
- [ ] Failing test (R2): brainstorming skill sets `phase=planning` + `phase_entered_at` on entry, clears with `phase_exit_artifact` on sign-off; implement in `skills/harness-brainstorming-plans/SKILL.md` + contract test
- [ ] Failing test: ambiguous implement-style prompts ⇒ Branch D, clear design work ⇒ B (`tests/unit/test_dispatcher.py`, `tests/unit/test_fallback_classify.py`)
- [ ] Implement bias-to-D rule in `classify_intent` prompt (`runtime/dispatcher.py:149`) + `prompt_classifier` fallback; D pre-flight asks 1–2 clarifying questions instead of escalating to B
- [ ] Failing test: toggle off ⇒ passthrough; waiver path sets `research_done`; wire toggle
- [ ] Author `skills/search-first/SKILL.md` — step 1 proportionality waiver, then Adopt/Extend/Compose/Build matrix, then **post-research depth checkpoint** (HITL `AskUserQuestion`: quick implementation w/ findings attached + clear `phase`, vs full planning pipeline; matrix outcome = recommended default); register in `skills.json` + contract test for checkpoint text
- [ ] Suite green; commit

## Phase 5 — F2 Adversary Pipeline (tiered + budgeted)
- [ ] Failing test: staleness checker — report exists + newer than design doc; toggle-off ⇒ pass (`tests/unit/test_adversary_pipeline.py`)
- [ ] Implement `scripts/check_risk_report.py` (no dispatcher gate — C3: insertion point doesn't exist)
- [ ] Failing test (R5): budget sidecar `state/budget_<session>.json` — counter increments per tool call, block past limit with summarize-and-finish message, no sidecar ⇒ passthrough, corrupt sidecar ⇒ fail-open, per-session isolation (`tests/hooks/test_dispatch_budget.py`)
- [ ] Implement budget backstop in `hooks/pre_tool_use.py` (R5 — same deterministic layer as TDD/F4 gates)
- [ ] Author `skills/adversary-pipeline/SKILL.md` — Tier 1: inline council-style role lenses (default, no subagents); Tier 2: Attacker→Defender→Auditor general-purpose dispatches, **skill writes the budget sidecar before each dispatch (R5)** (≤30 tool calls, ≤12 files, smaller model for Attacker/Defender, degrade-gracefully clause as steering before the enforced wall); council role-lens + GAN prompt-defense preamble; re-scope `agents/adversary.md` as Auditor
- [ ] Add skill-text gate to `harness-brainstorming-plans` + `harness-requesting-code-review` SKILL.md behind `pipeline.dispatcher.gates.adversary_exit`
- [ ] Register skill; update `tests/integration/test_claude_plugin_contract.py`
- [ ] Suite green; commit

## Phase 6 — Sticky Phase State Machine ⚠️ DEFERRED (outline in design doc Section 3; needs own HITL design pass — do NOT implement from the outline)
- [ ] Run its own design pass (Sections 0–4) covering: artifact-based exit-condition detection (the C3 gap), classifier shrink ("still in phase?" instead of re-classification), misroute suppression + user override, stale-phase reaping
- Persistence half already in scope per R2: phase keys + helpers (Phase 2), brainstorming-skill set/clear (Phase 4)
