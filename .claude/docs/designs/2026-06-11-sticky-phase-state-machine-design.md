# Phase 6a — Session Identity Repair (sticky-phase machinery deferred)

*Status: APPROVED — Sections 0–3 HITL-approved; Tier-1 adversarial review complete (risk report: [docs/adversary/2026-06-11-sticky-phase-state-machine-risk-report.md](../../../docs/adversary/2026-06-11-sticky-phase-state-machine-risk-report.md) — verdict: ready for sign-off, M1/M2 amendments folded into Section 3). **Scope: fix-only "Phase 6a" (HITL, 2026-06-11)**: stable session identity + /clear semantics + stale-state expiry + fallback-keyword unification. The sticky-mode machinery (ledger merge, artifact exit detection, classifier shrink, misroute suppression) is **deferred** — re-open as "Phase 6b" if within-conversation misrouting keeps hurting after this repair.*

**Why fix-only (HITL decision):** the identity defect is not a feature gap —
it silently breaks shipped behavior. Hooks resolve a stable fallback id (the
CLI's process id) while skill-invoked scripts resolve a fresh ephemeral shell
pid every call (observed live: `73171` → `80226` → `80490` in one
conversation). Consequence: `set-phase`/`set-research-done`/budget-arm writes
land in stores the enforcing hooks never read — the Phase 4 gate never
engages or releases via skills, and the Phase 5 Tier-2 budget wall never
binds. Additionally `/clear` does NOT clear hook-side state today (same CLI
process ⇒ same ppid ⇒ same store), violating the user's hard requirement
that a new session forgets everything.
*Date: 2026-06-11 · Parent: [2026-06-10-ecc-feature-port-design.md](2026-06-10-ecc-feature-port-design.md) Section 3 "Phase 6" (deferred outline)*
*Design inputs: 2026-06-11 code review of the Phase 4–5 slice (`698fd44...HEAD`) — guesser divergence (dispatcher fast-path vs deployed fallback), fragmented per-session state, and live-observed session-id drift (`73171` → `80226` → `80490` within one conversation).*

---

## Section 0 — Problem Understanding ✅ approved (full scope)

**The harness has no memory of what we're in the middle of.** Every message the
user sends, it plays a fresh guessing game — "is this a bug fix? a design
request? a question?" — and stamps a routing suggestion on the prompt. The
guess is made from the words in that one message, nothing else.

**Four concrete harms, all observed in the 2026-06-11 working session:**

1. **Mid-work misrouting.** During Phase 5 implementation, every message —
   "how do I test this", "run the reviews" — was stamped *"start a brand-new
   design session."* The assistant has to notice the stamp is wrong and ignore
   it, which works only when the assistant is paying attention.
2. **The guessers disagree with each other.** There are three copies of the
   guessing logic (the LLM classifier, its deployed keyword fallback, and a
   third fast-path in the tool plane). The 2026-06-11 review confirmed they
   contradict: the same message routes to *planning* in one and *direct
   implementation* in another (`dispatcher.py:226` vs
   `prompt_classifier.py` fallback). And when the LLM path is unavailable
   (observed: broken model config), the fallback runs 100% of the time.
3. **Modes can get stuck or vanish.** Phases 4–5 built the "write down the
   mode" half: planning mode blocks source edits until research is recorded.
   But *exiting* a mode relies on skill text remembering to run a script at
   sign-off. A crashed session leaves the mode set forever; nothing expires it.
4. **The session's memory is scattered and keyed to an unstable identity.**
   Per-session state lives in three files with three schemas
   (`session_memory_*`, `tdd_*`, `budget_*`), and the session id they key on
   falls back to the parent-process id, which *drifts between commands in the
   same conversation* (observed live: `73171` → `80226` → `80490`). Scripts
   invoked from skills get a fresh ephemeral shell parent every time — so the
   phase a skill sets, the research flag it records, and the store the
   enforcing hook reads can be **three different files**. The Phase 4 gate's
   plumbing is correct but stands on sand.

**Who hurts:** every engineer in every repo this harness is minted into, on
every prompt — misroutes waste turns, stuck gates block legitimate work,
split state makes gates fire (or release) wrongly, and trust in routing erodes.

**What Phase 6 delivers, in one sentence:** once a work mode starts, the
harness *remembers and respects it* — routing collapses to "are we still in
this mode? did it finish?", finish is detected from real evidence (a
signed-off design doc, a fresh risk report — not another guess), contradicting
guesses are suppressed, an explicit user override always wins, and abandoned
modes expire on their own.

**Scope decision (HITL, 2026-06-11):** session-id stability and unifying the
three classifier fallbacks are **in scope** — a sticky phase keyed to an
unstable id, or enforced by guessers that disagree, undermines the feature.

---

## Section 1 — Technical Plan (DRAFT, under review)

Plain English, six pieces, dependency-ordered. Each piece names the real
mechanism; exact files come in Section 3.

### 1. One stable session identity (the foundation)

Today `get_session_id()` checks env vars then falls back to the parent
process id — which is different for every Bash-invoked script (proof above).
The fix has three legs:

- **Hooks use the platform's truth.** Claude Code sends the real `session_id`
  inside the JSON payload every hook receives on stdin. We currently ignore
  it. Hooks will prefer payload id over env over ppid.
- **Hooks publish a pointer.** The active hook writes the id to a pointer file
  (`state/current_session`) so non-hook processes can find it.
- **Scripts take it explicitly, fall back to the pointer.**
  `session_phase.py` (and the budget arm/disarm) accept `--session <id>`;
  the SYSTEM STATE block prints the live id so skills can pass it through.
  No flag ⇒ read the pointer ⇒ only then the old env/ppid fallback.

*Concurrency caveat (in writing):* the pointer is last-writer-wins across
simultaneous sessions in one checkout. The explicit `--session` argument is
the precise path; the pointer covers the common single-engineer case.

**`/clear` semantics — a hard requirement (HITL, 2026-06-11).** `/clear`
means "start fresh," and the harness must honor that. Today it does NOT:
the ppid-keyed store survives `/clear` (the CLI process — and therefore the
parent pid — is unchanged), so a pre-`/clear` planning mode would keep
holding the gate afterwards. Keying the store to the **payload session id**
(which the platform renews per conversation) makes `/clear` an automatic,
guaranteed clean slate: new id ⇒ empty store ⇒ no mode, no gate, nothing to
escape. Modes are session-scoped by design; the value of stickiness lives
*within* one conversation (where all the observed misrouting happened), and
`/clear` is the correct boundary where remembering stops.
*Verification task (Section 3): empirically confirm the payload session id
changes across `/clear` on Claude Code; if any platform reuses it, fall back
to id+conversation-start-timestamp composite.*

### 2. One session ledger instead of three

Merge the TDD flag and the budget counters into the existing per-session
session-memory file: one schema, one atomic write helper
(`_save_session`'s tmp+rename), one retention policy. The review found the
three-file split already drifting: budget files gained pruning, `tdd_*` files
never had it (and a recycled session id can inherit a stale
`test_written: true`, silently bypassing the TDD gate). Gates read the old
file locations as fallback for one release, then the fallback is removed.

### 3. Artifact-based exit detection (closes the parent design's C3 gap)

On mode entry, record what "done" looks like next to the phase keys:
for `planning` — a design doc matching a recorded path pattern exists AND
(when `gates.adversary_exit` is on) a risk report newer than it (reusing
Phase 5's `check_risk_report.py` logic). On every prompt, the deployed
classifier (which already runs per prompt) does this cheap filesystem check;
if the evidence exists, it auto-clears the mode and says so in SYSTEM STATE.
The skill's explicit sign-off script remains the primary exit; detection is
the backstop for crashed or forgetful sessions. The dispatcher stays
untouched — it has no "design complete" insertion point (settled in the
parent design, C3).

### 4. Classifier shrink + one keyword table

While a mode is active, stop re-guessing: the deployed classifier
short-circuits to the mode's branch (planning ⇒ B), emits
"still in planning" in SYSTEM STATE, and **skips the LLM call entirely** —
faster, cheaper, deterministic, and immune to LLM outages mid-mode.

The three fallback guessers get **one shared keyword table**, generated into
both planes at mint, with a contract test asserting the tool-plane fast-path
and the deployed fallback classify a fixed prompt corpus identically —
directly fixing review finding #1 (dispatcher fast-path still routes
implement-verbs to B).

### 5. Misroute suppression + explicit user override

While a mode is active, dispatch stamps that contradict it are suppressed
(no more "start a design session" mid-build). The user always wins: an
explicit escape ("exit planning", "abandon the design") is detected
deterministically (keyword check, not LLM), confirmed once, and clears the
mode. SYSTEM STATE always shows the active mode and the escape phrase —
never mysterious.

### 6. Stale-mode expiry + toggle

A mode older than 7 days (configurable) is reaped by the existing retention
helper — a crashed session cannot leave a permanent gate. The whole feature
sits behind a new `pipeline.dispatcher.sticky_phase` toggle, dependent on
`services.session_memory` (compile-time validated like the Phase 0
dependency table).

### Ecosystem fit

Built entirely on shipped substrate — Phase 2's store, Phase 4's phase keys
and gate, Phase 5's freshness checker. Enforcement stays in the one
deterministic layer (`pre_tool_use.py`); detection lives in the deployed
classifier; the dispatcher remains advisory routing-only. The mechanical
2026-06-11 review fixes (brainstorming skill "optional" contradiction,
non-atomic budget write, tdd-prune gap, glob escaping, dead 'fix the'
keyword) ship as a small pre-Phase-6 hardening commit, independent of this
design.

---

> **Section 1 scope note (Phase 6a):** of the six pieces below, Phase 6a
> ships **piece 1** (identity + /clear), **piece 6's expiry half** (incl. the
> `tdd_*` prune gap), and **piece 4's keyword-table half** (fallback
> unification — review finding #1). Pieces 2, 3, 5, and piece 4's
> LLM-skip/shrink half are deferred to a future Phase 6b. The mechanical
> review fixes (atomic budget write, glob escaping, brainstorming "optional"
> contradiction, dead 'fix the' keyword, hoisted resolutions) fold into
> Phase 6a as hardening tasks — they touch the same files.

## Section 2 — Alternatives Considered ✅ approved (incl. /clear requirement promoted to Section 1)

**Just improve the guessers (better prompts, more keywords), keep per-prompt
re-classification.** Rejected: the misroutes are structural — the guesser has
no memory, so even a perfect guesser re-derives context it cannot see ("run
those reviews" carries no hint that we're mid-implementation). And the LLM
guesser can be *down entirely* (observed live: broken model config → 100%
fallback). Improving a guess is not a substitute for remembering.

**Host the sticky state in the dispatcher (tool plane).** Rejected — settled
in the parent design (M1, M5, C3): the dispatcher is advisory, has no session
id, cannot import the deployed plane's helpers, and has no "design complete"
insertion point. The deployed plane (classifier + pre_tool_use) owns state
and enforcement; the dispatcher stays routing-only.

**LLM-based exit detection ("does this conversation look finished?").**
Rejected: reintroduces nondeterminism at exactly the point determinism is the
goal — and it's unavailable when the LLM path is down. Artifacts (a design
doc on disk, a risk report newer than it) are checkable facts.

**Required `--session` flag with no pointer file (the minimal identity
variant).** Rejected by HITL choice (2026-06-11): a skill that forgets the
flag errors out mid-skill (better than silently writing to a dead store, but
still disruptive). The pointer file covers the common single-engineer case;
the flag remains the precise path for concurrent sessions.

**Exporting the session id into Bash environments so scripts inherit it.**
Rejected: the harness does not control how the platform propagates env vars
into skill-invoked shells (the observed ppid drift is exactly this gap).
Payload + pointer works without platform cooperation.

**File locks or SQLite for ledger concurrency.** Rejected — same YAGNI
rationale as the parent design: per-session JSON files written by short-lived
hook subprocesses; the existing atomic tmp+rename write is sufficient. The
ledger merge (piece 2) reduces the file count, not the locking model.

**Sharing the keyword table at runtime via import.** Rejected: the tool plane
cannot import deployed hooks (parent design M5). The table is *generated*
into both planes at mint, and a contract test asserts the two fallbacks
classify a fixed prompt corpus identically — drift fails CI instead of
failing users.

**Hard-muting all dispatch while a mode is active.** Rejected: the classifier
must keep running for exit detection and the user-override escape. Suppression
is targeted — only directives that *contradict* the active mode are dropped;
mode-consistent dispatch (e.g. the planning skill's own continuation) passes.

**Cross-session sticky modes (mode follows the user across `/clear` or into
a fresh conversation).** Rejected (HITL, 2026-06-11): `/clear` means "start
fresh" — that is a hard requirement, promoted into Section 1 piece 1 (today's
ppid-keyed store actually *violates* it; the payload-id fix is what delivers
it). The mode is deliberately **session-scoped**: new session id ⇒ empty
store ⇒ clean slate; the new session's first hook overwrites the pointer
file; the abandoned store is read by nobody and reaped after 7 days. The
*continuation* case (fresh conversation, same design work) is served by
suggestion, not stickiness: the existing "In-Progress Designs" SYSTEM STATE
line surfaces the unfinished design doc and the session may *offer* to
re-enter planning — the user opts in.

## Section 3 — Detailed Implementation (DRAFT, under review)

Three task groups, dependency-ordered. TDD mandatory: every task is
failing-test → minimal implementation → green → commit.

### Group 1 — Stable session identity (+ /clear semantics)

| File | Action | Rationale |
|---|---|---|
| `src/harness/templates/boilerplate/hooks/hook_common.py` | edit | `get_session_id(input_json=None)` gains the resolution order **(amended per risk-report M1)**: `HARNESS_SESSION_ID` (explicit override — preserves documented test/manual-injection semantics) → `input_json["session_id"]` (platform truth) → `CLAUDE_SESSION_ID`/`GEMINI_SESSION_ID` → **pointer file** `state/current_session` → ppid (last resort). New `publish_session_pointer(plugin_root, session_id)` — atomic tmp+rename write, fail-open. |
| `src/harness/templates/boilerplate/hooks/pre_tool_use.py` | edit | Parse stdin once, pass `input_data` to `get_session_id`; publish the pointer; resolve `session_id`/`plugin_root` ONCE before the gate chain (kills the 3× duplication — review efficiency finding). |
| `src/harness/templates/boilerplate/hooks/prompt_classifier.py` | edit | Same payload threading + pointer publish. Also unify plugin-root resolution on `resolve_plugin_root()` (kills the dual-resolution trap — review finding #7). |
| `src/harness/templates/boilerplate/hooks/session_memory_save.py`, `session_start.py`, `session_end.py` | edit | Thread payload session_id the same way (they already parse stdin). |
| `src/harness/templates/boilerplate/scripts/session_phase.py` | edit | Global `--session <id>` flag on all subcommands; no flag ⇒ pointer file ⇒ legacy env/ppid. New subcommands **`arm-budget`** (`--max-tool-calls 30 --max-file-reads 12`) and **`disarm-budget`** — replaces the SKILL.md heredocs (review finding #4) and uses the same atomic write helper. |
| `src/harness/runtime/context_builder.py` | edit | SYSTEM STATE gains a `Session: <id>` line so skills can pass `--session` explicitly; `prompt_classifier`'s inline fallback carries the same line. |
| `src/harness/templates/boilerplate/skills/adversary-pipeline/SKILL.md` | edit | Heredocs → `session_phase.py arm-budget/disarm-budget --session <id from SYSTEM STATE>`. |
| `src/harness/templates/boilerplate/skills/harness-brainstorming-plans/SKILL.md`, `skills/search-first/SKILL.md` | edit | Script invocations pass `--session <id from SYSTEM STATE>`. Brainstorming also fixes the "optional adversarial review" contradiction at the Execution-Handoff line (review finding #3). |
| `tests/hooks/test_session_identity.py` | create | TDD: payload id preferred over env/ppid; pointer published atomically + read by scripts; `--session` wins over pointer; ppid only as last resort; **/clear simulation** — two hook invocations with different payload ids never share a store; pointer last-writer-wins documented behavior. |
| `tests/hooks/test_search_first_gate.py` | edit | Regression for the live-loop bug: hook engages gate from payload id; `session_phase.py set-research-done --session <same id>` releases it (the exact loop that was broken). |
| `tests/hooks/test_dispatch_budget.py` | edit | Wall binds when armed via `arm-budget --session <hook's id>`; disarm removes it. |
| `tests/unit/test_adversary_pipeline.py` | edit | Contract tests updated: skill text must use arm-budget/disarm-budget + `--session`, no python heredocs. |

*Manual smoke (progress doc items, not pytest):* (1) in a live Claude Code
session, log the payload session id, `/clear`, log again — confirm it
changes (if a platform reuses ids, fall back to id+start-timestamp
composite); (2) **risk-report M3** — arm `max_tool_calls=2`, dispatch a
trivial subagent, confirm the budget wall blocks its third call (verifies
subagent hook payloads inherit the parent session id).

### Group 2 — Stale-state expiry completion

| File | Action | Rationale |
|---|---|---|
| `src/harness/templates/boilerplate/hooks/hook_common.py` | edit | `prune_old_session_files` gains `tdd_*.json` (mtime-aged, like budget) — closes the unbounded-accumulation + recycled-id TDD-bypass gap (review finding #6). Pointer file exempt (single, overwritten). |
| `tests/hooks/test_dispatch_budget.py` or `tests/hooks/test_session_memory.py` | edit | TDD: old `tdd_*.json` pruned; fresh kept. |

### Group 3 — Fallback-keyword unification (review finding #1)

| File | Action | Rationale |
|---|---|---|
| `src/harness/runtime/fallback_keywords.py` | create | THE single keyword table (branch → keyword list, with precedence order). Lives in the runtime slice so BOTH planes consume one source: the tool-plane dispatcher imports it directly; the deployed `prompt_classifier` imports it from the minted `src/` (already on its sys.path — parent design M5). Includes the bias-to-D verbs in D, restores bare `'which'` to C (review finding #2), drops the dead `'fix the'` D-entry and documents A's `'fix'` precedence (review finding #9). |
| `src/harness/init/runtime_slice.py` | edit | Add `fallback_keywords.py` to the copied-module map so minted plugins receive it. |
| `src/harness/runtime/dispatcher.py` | edit | **(Amended per risk-report M2)** extract the inline keyword block (`classify_intent`, ~line 226) into a module-level `keyword_fast_path(prompt)` consuming the shared table; `classify_intent` calls it. Implement/build/create/new now route D, matching everything else — and the parity test can import the function directly without touching the LLM path. |
| `src/harness/templates/boilerplate/hooks/prompt_classifier.py` | edit | `fallback_classify` consumes the table when importable; keeps its inline copy ONLY as an import-failure fallback, with parity enforced by the contract test below. |
| `tests/unit/test_fallback_parity.py` | create | TDD: a fixed prompt corpus (≥20 prompts covering A–E, incl. 'which approach…', 'implement the feature', 'fix the typo') classifies **identically** through the dispatcher fast-path and `fallback_classify`; drift fails CI. |
| `tests/unit/test_dispatcher.py`, `tests/unit/test_fallback_classify.py` | edit | Re-point existing keyword assertions at the shared table semantics. |

### Hardening folded in (same files, same commits)

- Atomic budget-sidecar write (tmp+rename) + check-before-write ordering so
  blocked calls don't consume budget (review finding #5) — `pre_tool_use.py`,
  covered in `test_dispatch_budget.py`.
- Glob-escape the topic in `check_risk_report.py` (review finding #8) —
  `glob.escape`, test with a bracketed design-doc name.
- Shared `_deny(msg, is_gemini)` helper replacing the five copy-pasted
  block-and-exit stanzas in `pre_tool_use.py` (reuse finding).

### Cross-phase invariants

- After every group: `python3 -m pytest` and `python3 -m pytest
  tests/integration` fully green.
- New runtime-slice module registered in the update plane via the existing
  slice map (no manifest changes needed — slice files are already producers).
- No new toggles: Phase 6a repairs existing toggled features; the
  `sticky_phase` toggle ships with Phase 6b if/when it happens.
- Live delivery after merge: `harness-wf update` + the Section 3 manual
  /clear smoke.

### Deferred to Phase 6b (own design pass when re-opened)

Ledger merge (one file/schema), artifact-based exit detection, classifier
shrink (skip LLM mid-mode), misroute suppression + user-override escape,
`pipeline.dispatcher.sticky_phase` toggle.

## Section 4 — Adversarial Review ✅ complete (Tier 1, 2026-06-11)

First production run of the Phase 5 `adversary-pipeline` skill (Tier 1:
inline Attacker/Defender/Auditor lenses). Full report:
`docs/adversary/2026-06-11-sticky-phase-state-machine-risk-report.md`.

- Critical: none — both load-bearing mechanism claims verified against the
  tree (`prompt_classifier.py:138-139` sys.path insert; `runtime_slice.py`
  registration point).
- Major: M1 (identity resolution order — explicit env override outranks
  payload) and M2 (extract `keyword_fast_path` for parity testability)
  **folded into Section 3**; M3 (subagent budget-wall binding) added to the
  manual-smoke checklist.
- Minor: m1–m4 accepted with documented degradation paths.
- **Verdict: ready for sign-off.**
