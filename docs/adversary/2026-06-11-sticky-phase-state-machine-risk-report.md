# sticky-phase-state-machine — Adversarial Risk Report

*Design: .claude/docs/designs/2026-06-11-sticky-phase-state-machine-design.md · Reviewed: 2026-06-11 · Tier: 1 (inline council — Attacker/Defender/Auditor lenses)*
*First production use of the Phase 5 adversary-pipeline skill.*

## Critical (block sign-off)

None. The two load-bearing mechanism claims were verified against the tree:
the deployed `prompt_classifier` already puts the minted `src/` on `sys.path`
(`prompt_classifier.py:138-139`), so the shared keyword table import path is
real; the runtime-slice map (`src/harness/init/runtime_slice.py:44-57`) is
the established registration point for the new module.

## Major (resolved as design amendments before sign-off)

- **M1 — Identity resolution order: explicit override must outrank payload.**
  The drafted order (payload → env → pointer → ppid) breaks
  `HARNESS_SESSION_ID`'s documented "explicit override for testing or manual
  injection" semantics (hook_common.py:34) and the e2e tests built on it.
  *Defender resolution:* order is `HARNESS_SESSION_ID` (explicit override) →
  payload session_id (platform truth) → platform env (`CLAUDE_SESSION_ID`/
  `GEMINI_SESSION_ID`) → pointer → ppid. **Folded into Section 3 Group 1.**
- **M2 — Dispatcher fast-path is not independently testable as written.**
  The keyword block lives inline in `classify_intent` after the LLM attempt
  (`dispatcher.py:226`); the parity corpus test cannot reach it without
  invoking the LLM path. *Defender resolution:* extract it as
  `keyword_fast_path(prompt)` consuming the shared table; `classify_intent`
  calls it; the parity test imports it directly. **Folded into Section 3
  Group 3.**
- **M3 — Subagent budget-wall binding remains empirically unverified.**
  Whether a Task-dispatched subagent's hook payloads carry the parent's
  session_id (so the armed sidecar binds it) is PLAUSIBLE but unproven —
  carried from the 2026-06-11 Phase 4–5 code review (finding #10).
  *Defender resolution:* added to the Section 3 manual-smoke list alongside
  the /clear check (arm max_tool_calls=2, dispatch a trivial subagent,
  observe the block). Not a blocker for Phase 6a: the identity repair
  strictly improves the current state (today the wall binds nothing).

## Minor (accepted / noted)

- **m1 — Gemini hook payloads may not carry session_id** (unverified, parent
  design M4 territory). Accepted: the resolution chain degrades to platform
  env → pointer → ppid; gemini hooks' ppid is expected stable per-process.
- **m2 — Pointer file must be exempt from pruning.** It is (`current_session`
  has no `.json` suffix; prune globs are `*_*.json`), but the Section 3 test
  list now asserts it explicitly.
- **m3 — Parity corpus must pin precedence, not just membership.** 'fix the
  typo' → A (A's 'fix' outranks D) is order-dependent; the corpus test
  encodes precedence as part of the contract.
- **m4 — Pointer last-writer-wins across concurrent sessions** in one
  checkout: documented accepted risk; `--session` is the precise path
  (HITL-approved variant).

## Verdict

**Ready for sign-off** with amendments M1 and M2 folded into Section 3
(done in the same revision as this report). M3/m1 are empirical checks on
the live-delivery checklist, not design gaps.

*Re-issued post-amendment (2026-06-11): confirmed the Section 3 folds match
M1 (HARNESS_SESSION_ID → payload → platform env → pointer → ppid) and M2
(`keyword_fast_path` extraction) verbatim; M3 added to the manual-smoke
list. No further findings. — Auditor*
