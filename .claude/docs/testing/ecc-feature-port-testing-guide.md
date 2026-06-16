# ECC Feature Port — Per-Phase Testing Guide (Phases 0–6a)

*How to verify every phase of the ECC feature port, both the automated suite
and hands-on smoke tests against the live deployed plugin
(`.claude/harness-wf-plugin/`). Written 2026-06-12 alongside the
`feat/ecc-feature-port` PR.*

## The automated layer (run first, always)

```bash
python3 -m pytest                      # full suite
python3 -m pytest tests/integration    # integration slice
```

Per-phase test slices:

| Phase | Slice |
|---|---|
| 0 — toggles | `pytest tests/hooks/test_feature_toggles.py tests/unit/test_features_loader.py tests/unit/test_cli_features_sync.py` |
| 1 — rules packs | `pytest tests/unit/test_rules_packs.py` |
| 2 — session memory | `pytest tests/hooks/test_session_memory.py` |
| 3 — continuous learning | `pytest tests/hooks/test_session_end_learning.py tests/unit/test_skill_extraction.py` |
| 4 — search-first gate | `pytest tests/hooks/test_search_first_gate.py` |
| 5 — adversary pipeline | `pytest tests/unit/test_adversary_pipeline.py tests/hooks/test_dispatch_budget.py` |
| 6a — session identity | `pytest tests/hooks/test_session_identity.py tests/unit/test_fallback_parity.py tests/unit/test_render.py` |

## Environment prerequisites for live testing

1. **Live plugin must be current:** `harness-wf update --project-path "$PWD"`
   (then `--check` should report zero apply/conflict verdicts).
2. **LLM classifier paths need a working model.** If
   `~/.claude/settings.json` pins a nonexistent model, every headless
   `claude -p` call 404s: intent classification permanently falls back to
   keywords and Phase 3 extraction cannot run. Fix or remove the `model` key
   before testing Phase 3 or LLM routing.

## Phase 0 — Feature toggles (operator YAML → compiled JSON)

```bash
# Flip any key in .claude/harness-wf-plugin/features.yaml, then:
harness-wf features sync --project-path "$PWD"      # compiles features.json
# Skip the sync → your next prompt's SYSTEM STATE shows a staleness warning.
# Dependency validation: set services.session_memory.enabled: false while
# pipeline.dispatcher.gates.search_first: true → sync FAILS naming the dependency.
```

## Phase 1 — Stack-aware rules packs

- `ls .claude/rules/harness/` → `common/` + packs for the detected stack only
  (no `golang/` in a Python/TS repo).
- Touch a `.py` file mid-session → python pack rules lazy-load into context
  (`paths` frontmatter). Non-matching files don't load them.
- Hand-edit a file inside `.claude/rules/harness/` then
  `harness-wf domain-refresh --project-path "$PWD"` → your edit is
  overwritten (generated-mirror semantics, by design).

## Phase 2 — Session memory

- After any assistant response: `ls .claude/harness-wf-plugin/state/session_memory_*.json`.
- Start a new session → SessionStart injects a digest of prior session entries.
- `HARNESS_SESSION_CONTEXT=off claude` → no injection (opt-out).
- Retention: state files older than 30 days are pruned at session start.

## Phase 3 — Continuous learning (needs working LLM; ≥10-turn session)

- End a session of 10+ turns, then:
  `cat .claude/harness-wf-plugin/state/learning_extraction.log` (spawn log) and
  `ls ~/.local/share/harness-wf/projects/*/learned/` (extracted SKILL.md files).
- Next session start injects ≤6 learned-skill summaries.
- `/learn` triggers the same extraction on demand.

## Phase 4 — Search-first gate (deterministic, 30-second demo)

```bash
P=.claude/harness-wf-plugin
SID=$(grep -m1 . $P/state/current_session 2>/dev/null || echo demo)
python3 $P/scripts/session_phase.py set-phase planning --session "$SID"
# → ask Claude to edit any .py source file: PreToolUse blocks (exit 2,
#   "Search-First gate"). Then release it:
python3 $P/scripts/session_phase.py set-research-done --session "$SID" --note "waiver: demo"
# → same edit passes the search gate (TDD gate may still apply — that's the
#   other gate working). Clean up:
python3 $P/scripts/session_phase.py clear-phase --session "$SID"
```

Your live session id is printed in every prompt's SYSTEM STATE (`Session: <id>`).

## Phase 5 — Adversary pipeline

```bash
P=.claude/harness-wf-plugin
# Staleness checker against a design doc with no risk report → exit 1 "missing":
python3 $P/scripts/check_risk_report.py \
  .claude/docs/designs/2026-06-11-sticky-phase-state-machine-design.md \
  --reports-dir docs/adversary
# That one passes (report exists & fresh). Touch the design doc → re-run → exit 1
# "stale" (freshness enforcement). git checkout the design doc afterwards.
```

- Full skill: run `adversary-pipeline` against any design doc → Tier 1 writes
  `docs/adversary/<date>-<topic>-risk-report.md` → checker passes.
- The brainstorming skill's sign-off invokes the checker automatically when
  `pipeline.dispatcher.gates.adversary_exit` is on.

## Phase 6a — Session identity repair

**Automated already proves:** payload-id resolution order, pointer publish,
/clear simulation (different payload ids never share a store), the repaired
live loop (hook engages gate ↔ script releases it), budget wall binding.

**Manual smoke 1 — /clear means fresh:**
1. Note the `Session: <uuid>` line in any prompt's SYSTEM STATE block.
2. Type `/clear`.
3. Ask anything; compare the `Session:` line — a different id confirms a
   fresh store (no inherited phase/gates/budget).

**Manual smoke 2 — M3, budget wall binds subagents:**
```bash
P=.claude/harness-wf-plugin
SID=<the Session id from SYSTEM STATE>
python3 $P/scripts/session_phase.py arm-budget --session "$SID" --max-tool-calls 2
# → dispatch any trivial subagent (e.g. "use a subagent to count files in src/")
#   and confirm its 3rd tool call is blocked with "summarize what you have".
python3 $P/scripts/session_phase.py disarm-budget --session "$SID"   # ALWAYS disarm
```
⚠️ While armed, the budget throttles every tool call resolving to that session
id — including yours. Disarm immediately after the check.

**Identity loop (scriptable, no conversation needed):**
```bash
P=.claude/harness-wf-plugin
echo '{"session_id": "smoke", "tool_name": "Bash", "tool_input": {"command": "ls"}}' \
  | env -u HARNESS_SESSION_ID -u CLAUDE_CODE_SESSION_ID CLAUDE_PLUGIN_ROOT="$PWD/$P" \
    python3 $P/hooks/pre_tool_use.py
cat $P/state/current_session            # → smoke   (hook published the pointer)
env -u HARNESS_SESSION_ID -u CLAUDE_CODE_SESSION_ID CLAUDE_PLUGIN_ROOT="$PWD/$P" \
  python3 $P/scripts/session_phase.py set-phase planning
ls $P/state/session_memory_smoke.json   # → script reached the hook's store
# cleanup:
env -u HARNESS_SESSION_ID -u CLAUDE_CODE_SESSION_ID CLAUDE_PLUGIN_ROOT="$PWD/$P" \
  python3 $P/scripts/session_phase.py clear-phase
rm -f $P/state/session_memory_smoke.json $P/state/current_session
```

## End-to-end mint test (fresh project)

```bash
mkdir /tmp/mint-smoke && cd /tmp/mint-smoke && git init -q
harness-wf init --project-path "$PWD"
# Assert: .claude/harness-wf-plugin/{features.yaml,features.json,
#   skills/adversary-pipeline/,scripts/check_risk_report.py,
#   scripts/session_phase.py,src/fallback_keywords.py,hooks/session_end.py}
# and .claude/rules/harness/ packs matching the detected stack.
```

## Known caveats

- **Pointer file is last-writer-wins** across concurrent sessions in one
  checkout; the `--session` flag (id from SYSTEM STATE) is the precise path.
- **Manual edits to live plugin .py files** read as operator customizations to
  the updater; if `update --check` reports conflicts on generated hooks,
  `update --force` takes theirs (they are generated files).
- **gemini hook payloads carrying `session_id` is unverified** (risk-report
  m1); the resolution chain degrades to env → pointer → ppid there.
