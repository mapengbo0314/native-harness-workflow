# `src/harness` Full Review — Issues Report (2026-06-12)

Severity scale per `.claude/rules/harness/common/baseline.md`:
**CRITICAL** = block | **HIGH** = should fix | **MEDIUM** = consider | **LOW** = optional.

> **Resolution status — updated 2026-06-15** (branch `feat/ecc-feature-port`)
> - ✅ **Resolved:** C1, C2, C3, C4 (all CRITICALs), H5, H6, H9, M1, M4, M6, M7 (docstrings), M9, all easy LOW (asserts, `_missing_verdict`), **H4, M10, H8**.
> - 🟡 **Partial:** M7 (docstrings fixed; `base.py` S2-T3/T4 shim removal still open).
> - ⬜ **Open:** H1–H3, H7, M2–M3, M5, M8, remaining LOW (F541, E402).
> - 🗑 **Corrected/retracted:** H8's "36 files" figure was stale. Path typos: `minting_engine.py` lives in `init/`, not `runtime/`.
> Each item below is annotated inline. Verified by pyflakes + unit / integration / e2e+hooks suites.

---

## CRITICAL / fix ASAP

### ✅ C1. Live routing is permanently degraded by an unguarded model pin (environmental, but the code amplifies it)
**RESOLVED (2026-06-14):** `llm_client.py` now raises a non-retryable `LLMConfigError` for
404/model-not-found (deterministic errors skip the retry loop), added a `stop_after_delay(45)`
hard deadline, and `dispatcher.classify_intent` caches the broken-LLM verdict
(`state/llm_health.json`, 300s TTL) so subsequent prompts skip straight to keyword fallback.
Tests: `test_llm_client_failfast.py`, `test_dispatcher_llm_cache.py`.
`runtime/llm_client.py` + `runtime/dispatcher.py:classify_intent`: when the configured CLI
model is invalid (as it is right now — `~/.claude/settings.json` pins a nonexistent
`gemini-3.5-flash` model), **every user prompt** pays: subprocess spawn → 404 →
tenacity retry ×3 with exponential wait (5–20s between attempts) → keyword fallback. That is
up to ~30–60s of dead latency injected into the UserPromptSubmit hot path on *every prompt*,
plus the retry noise visible in the transcript.
**Fix:** (a) don't retry on a 404/"model not found" class of error — it's deterministic, retrying
is pure waste; parse the error and fail fast to the keyword path; (b) cache the "LLM is broken"
verdict in the session store for N minutes so subsequent prompts skip straight to fallback;
(c) `query_llm` timeout=30 × 3 attempts inside a synchronous prompt hook needs a hard overall
deadline.

### ✅ C2. `prompt_classifier.py` reads keys the dispatcher never produces
**RESOLVED (2026-06-14):** `dispatch_agent` now returns `intent_justification`, and the
classifier reads `missing_documents` (not `artifacts_missing`). Schema regression test added:
`test_dispatch_agent_schema.py`.
`templates/boilerplate/hooks/prompt_classifier.py:170-190`:
- `result.get("intent_justification")` — `dispatch_agent` returns no such key → `reason` is
  always `None` on the primary path.
- `routing_decision.get("artifacts_missing", [])` — `evaluate_artifacts` returns
  `missing_documents`, not `artifacts_missing` → "Missing Documents" in SYSTEM STATE is always
  `None` regardless of actual state.
These are silent contract mismatches in the core routing pipeline. Fix the key names (and add
a test asserting the dispatcher result schema against the classifier's reads).

### ✅ C3. `_validate_claude_plugin` retry logic is a no-op (runs the identical command twice)
**RESOLVED (2026-06-14):** extracted `_run_plugin_validate()` (single run, raise on failure);
deleted the dead retry branch. Test: `test_validate_plugin_no_retry.py`.
`init/cli.py:149-170`: `cmd` and the first `subprocess.run` argument are the *same list*; the
"fallback" branch re-runs the exact same command it just ran. Whatever flag-degradation
behaviour this intended (strip `--strict`?) does not exist. Either implement the intended
fallback or delete the dead branch.

### ✅ C4. `pre_tool_use.json` log grows unbounded and is rewritten in full on every tool call
**RESOLVED (2026-06-14):** new `_append_tool_log()` does O(1) JSONL append + size-based
rotation to `<name>.1` at 5 MB; log renamed `.json`→`.jsonl`. Test: `test_pre_tool_use_log.py`.
`templates/boilerplate/hooks/pre_tool_use.py:310-328`: every tool call reads the whole JSON
array, appends, and rewrites it. O(n²) over a session's tool calls in the synchronous
PreToolUse hot path, with no rotation or cap. Long-lived projects will see every tool call get
progressively slower. Fix: JSONL append (`open(..., "a")`) + size-based rotation, or drop the
log entirely (nothing in the repo reads it).

---

## HIGH

### H1. `init/cli.py:main` — 412-line god function
Violates the repo's own ≤50-line rule by 8×. It interleaves: platform prompt, path
normalization, atomic-swap setup, minting, plugin generation, root-staging merge, smart merge,
backup rotation, feature recompile, packs re-sync, embedded setup, manifest stamping, domain
seed, and final printing. Extract: `run_init(args)` → `select_platform()`, `mint_to_temp()`,
`merge_root_staging()`, `swap_into_place()`, `finalize_plugin()`. `mint_workspace` (297 lines)
and `run_update` (107) need the same treatment.

### H2. ClaudeAdapter duplicates the canonical hook-response logic
`adapters/claude.py:227-276` is a hand-maintained copy of
`adapters/runtime_adapter.py:format_hook_response` (the generalist remap and CTA string are
hardcoded instead of profile-driven). Gemini, Codex, and Cursor already delegate; Claude is the
one platform left on the copy. The byte-identity test pins it, but the right fix is the same
3-line delegation the other adapters use — then the duplication and its test burden disappear.

### H3. `install_hooks` placeholder-rewrite loop copy-pasted 4×
The identical walk-files / replace-`${HARNESS_PLUGIN_ROOT}` / regex-replace-`.claude` loop
appears in `gemini.py:31-63`, `codex.py:39-57`, `cursor.py:39-57`, and (with additions)
`claude.py:76-98`. Extract one `rewrite_deployed_placeholders(dir, env_var, config_dir,
event_mappings=None)` helper in `adapters/base.py` or a shared module; the gemini event-name
remap and Claude hooks-injection stay as the per-platform extras.

### ✅ H4. Platform-choice digit map duplicated in 3 places
**RESOLVED (2026-06-15):** extracted leaf module `harness/init/platforms.py`
(`PLATFORM_BY_DIGIT` + `platform_name_from_choice` + `harness_folder_from_choice`);
`cli.py` and `minting_engine.py` now both import it. The folder map collapses to
`"." + name` with an `.agents` fallback — proven behavior-identical to the old
if/elif. (The review's `load_profile(name).config_dir` idea doesn't fit the
`agents` alias, which has no profile; the leaf-module approach is simpler and
cycle-free.) TDD: `tests/unit/test_platform_digit_map.py`.
~~`cli.py:_platform_name`, `minting_engine.py:45`, `minting_engine.py:179` all hold
`{"1": "gemini", "2": "claude", "3": "cursor", "4": "agents", "5": "codex"}` — and
`cli.py:783-792` re-derives the same mapping a 4th time as if/elif for `harness_folder`
(whose values duplicate `config_dir` from the profiles). One constant + lookup of
`load_profile(name).config_dir` removes all four.~~

### ✅ H5. Unused import in `claude.py` is the *cause* of the documented circular import
**RESOLVED (2026-06-14):** deleted the unused `generate_orchestrator_plugin` import from
`adapters/claude.py`. (The lazy-import workarounds in `plugin_generator.py` were left in place
for now — safe to simplify in a follow-up.)
`adapters/claude.py:7` imports `generate_orchestrator_plugin` and never uses it. This is
exactly the cycle `plugin_generator.py:18-22` documents and works around with lazy imports
(`plugin_generator → profile → adapters/__init__ → claude → plugin_generator`). Delete the
import and the lazy-import workarounds become unnecessary.

### ✅ H6. Dead code shipped into every minted plugin: `init/discovery_engine.py`
**RESOLVED (2026-06-14):** deleted the module and its `RUNTIME_FILE_MAP` entry (so it no longer
ships into any plugin); `update/classification.py` + `minting_engine.py` derive from the map, so
removal propagates cleanly. Repointed the one real `query_llm` caller (`tests/sandbox/runner.py`)
to `harness.runtime.llm_client`; dropped 5 vestigial mint-path mocks that targeted a namespace
mint never imports. Gate run **offline** (no `claude`/`gemini` on PATH): unit 999, integration 50,
sandbox 16, e2e 137 — all green. Adversary-reviewed GO.
Its public functions (`acquire_mcp_context`, `fetch_skill`, `fetch_remote_skill`, a duplicate
`TemplateRenderer`) have **zero production callers** — only tests patch
`discovery_engine.query_llm` (which is itself an unused re-import from `llm_client`). Yet
`RUNTIME_FILE_MAP` ships it into every plugin's `src/`. Remove the file from the slice (and
repoint the tests to patch `harness.runtime.llm_client.query_llm`), or delete the module.

### H7. `GenericAdapter` drifts from the `generic` profile (and is untested for parity)
`adapters/generic.py` hardcodes name/dirs/formats that duplicate the `generic` entry in
`platform_profiles.json`, and its `format_hook_response` shape (`system_prompt_extension`,
extra `target_agent` key) differs from what `RuntimeAdapter("generic")` emits at runtime
(claude-shaped output). The parity test parametrizes only claude/gemini/codex/cursor, so this
mint-vs-runtime divergence is real and unpinned. Make GenericAdapter profile-driven and add it
to the parity matrix (or document why generic is exempt).

### ✅ H8. Codegraph index is stale and lying — *resolved locally (2026-06-15)*
**RESOLVED (local-only; `.codegraph/` is gitignored, nothing committed):** clean-rebuilt
the index. Key findings for future reference:
- **`sync`/`index` are additive — they do NOT garbage-collect nodes for deleted files.**
  Only `index --force` rebuilds the node table and drops phantoms (`ghost.py`,
  `test_update_ghost.py` are gone now).
- The default config didn't exclude the deployed `.claude/harness-wf-plugin/` mirror or
  vendored `benchmark/`, so every hook was double-indexed. Added `**/.claude/**` +
  `**/benchmark/**` to `.codegraph/config.json` excludes → 347→**225 files**, no dup symbols.
- **MCP retrieval never auto-reindexes** (the server just reads the static DB). The
  package's auto-update path is the hook pair `mark-dirty` + `sync-if-dirty`, which is
  **not wired** in this repo's settings — worth adding so the index self-maintains.


**CORRECTED:** the "**36 files**" figure was itself stale — the index has since been re-indexed
and now reports **188 files**, so the headline claim is no longer true. The underlying staleness
sub-point still holds: codegraph still returns `update/ghost.py` (`split_ghost_injection`) even
though that file is deleted on disk, and a `domain/` path query returns nothing despite the
package existing. So: re-index is still worth wiring into a hook/CI step, but this is no longer a
"36 files / missing domain/" situation. (Original text below, kept for history.)
~~The index reports 36 files including `update/ghost.py` (deleted) while missing `domain/`,
`init/rtk.py`, `init/features.py`, `runtime/fallback_keywords.py`, and several hooks.~~ Anyone
following the project's "graph-first" rule gets wrong answers. Re-index, and consider wiring
the re-index into a hook or CI step.

### ✅ H9. Stale `__pycache__` for deleted modules + local test debris in the templates tree
**RESOLVED (2026-06-14):** removed orphan bytecode for deleted modules and the
`boilerplate/state/session_memory_*.json` debris. (Ephemeral — `__pycache__` regrows on run,
but orphans for deleted sources will not return.)
Not committed (gitignored) but present on disk: bytecode for long-deleted modules
(`harness/dispatcher`, `domain/{compile,merge,reconcile,serialize,slice}`,
`runtime/platform_adapter_{claude,gemini,codex,cursor,generic}`) and
`templates/boilerplate/state/session_memory_*.json` test-session files. The mint copy ignores
`state/`, but the stale bytecode can shadow/confuse imports and grep results. `find src -name
__pycache__ -exec rm -rf {} +` and clean the boilerplate `state/`.

---

## MEDIUM

### ✅ M1. 36 ruff F-class findings (29 unused imports, 6 redefinitions, 1 unused var)
**RESOLVED (2026-06-14):** cleared all unused imports / redefinitions across `cli.py`,
`dispatcher.py`, `minting_engine.py`, `hook_common.py`, `domain/server.py`, `features.py`,
`adapters/claude.py` (used `pyflakes` as the oracle since ruff isn't wired; it also caught
3 extras: `claude.py` `Optional`+`shlex`, `cli.py` `_json`). pyflakes now reports zero F-findings
on these. CI wiring for ruff is still open.
All auto-fixable (`ruff check src/harness --select F401,F811,F841 --fix`). Highlights:
- `cli.py`: `getpass`, `logging`, top-level `time` unused (then re-imported mid-function at
  line 804); `Path`, `load_profile`, `read_manifest`, `_migrate_b0_paths` re-imported.
- `dispatcher.py`: `time`, `re`, `subprocess`, `sys`, `Optional` all unused.
- `minting_engine.py`: `urllib.request`, `difflib` (re-imported locally), `TemplateRenderer`,
  `render_template`, `generate_orchestrator_plugin` unused.
- `hook_common.py`: `tempfile`, `shutil`, `contextmanager` unused.
- `domain/server.py`: `TOPICS` unused. `features.py`: `sys` unused.
Repo has no ruff config wired into CI for `src/harness` — add it (the python rules pack the
harness itself ships mandates ruff).

### M2. Mid-file imports and module-level side effects in `cli.py`
Imports at lines 90-94 after executable code, `load_dotenv()` + langfuse env mutation at
import time, and `@observe()` decorating `main`. The import-order dance is documented for
langfuse, but the structure makes the module untestable without env side effects. Move the
langfuse bootstrap into a function called from `main()`, hoist imports.

### M3. `mint_workspace` walks the whole tree twice and rewrites files in place
Pass 1 and Pass 2 each re-walk and rewrite. Fine at current scale, but each file is also read
even when unchanged. Single walk with both passes per file is not possible (cross-file include
ordering — documented), but Pass 2 could skip files with no `@` lines cheaply.

### ✅ M4. `perform_smart_merge` catch `(UnicodeDecodeError, Exception)` — redundant tuple
**RESOLVED (2026-06-14):** collapsed to `except Exception as e` (`init/minting_engine.py:363` —
the review's `runtime/...:368` path/line was off). The deeper "silently downgrades merge
failures to a Skipping-merge print" concern is left as-is (out of easy-fix scope).
~~`minting_engine.py:368`.~~ `Exception` already covers it; the tuple suggests an intent to handle
decode errors specially that never materialized. Also the bare `except Exception` around
merges silently downgrades real merge failures to a "Skipping merge" print.

### M5. Hardcoded `.claude/harness-wf-plugin` in ~6 places
`cli.py` (lines 298, 378, 397-398), `minting_engine.py:_read_domain_stack:565`,
`dispatcher.py` comments/logic. `profile.domain_root_rel()` exists to own this. Thread it
through instead — anyone renaming the plugin dir via the profile today would break these
call sites silently.

### ✅ M6. `pre_tool_use.is_dangerous_rm_command` over-blocks
**RESOLVED (2026-06-14):** anchored `r'/'`→`r'(?:^|\s)/'` (still catches any absolute path) and
`r'\.'`→`r'(?:^|\s)\.(?:\s|$)'` (bare current dir only), so `rm -r build/dist` / `./build` /
`my.folder` are no longer false-positives while `/`, `/etc`, `~`, `..`, `.` stay blocked. TDD
test added: `tests/unit/test_pre_tool_use_dangerous_rm.py`. **Scope note:** the over-block only
ever bit the non-force `rm -r` form — `rm -rf`/`rm -fr` short-circuit on the force-recursive
patterns *before* the path list is consulted, so the path list was already dead for `-rf`.
~~`dangerous_paths` includes `r'/'` and `r'\.'` — any `rm -r <path>` containing a slash or dot
(i.e. virtually all of them) is blocked, making the earlier fine-grained patterns dead code.~~

### 🟡 M7. `update/__init__.py` docstring is stale
**PARTIAL (2026-06-14):** fixed the two stale docstrings — `update/__init__.py` now reads
"(detection, apply, journal, conflict, migration)", and `runtime_adapter.py` now cites the real
pin `tests/unit/test_runtime_adapter.py` (dropping the non-existent
`test_adapter_drift_guard.py` and the deleted-standalone-files clause). **Still open:** the
`copy_runtime_modules` S2-T7 docstring note and the S2-T3/T4 `base.py` shim removal — left for a
follow-up since they entail real migration work, not a docstring edit.

### M8. `session_end.py` lockfile race + leaked payload files — *partly overstated (adversary 2026-06-15)*
**CORRECTION:** the "never cleaned up if `extract_skills.py` crashes" claim is mostly false —
`extract_skills.py` unlinks the payload in a `finally:` block, so normal exceptions are covered.
The only leak path is a hard SIGKILL/power-loss before the `finally`. **True sub-point:**
`prune_old_session_files` (prunes `session_memory_*`, `budget_*`, `tdd_*`, `*.tmp`,
`*.budget-tmp`) doesn't include `learning_input_*`. Net: a **one-line** belt-and-suspenders add
for the kill-9 edge — low value, not the hygiene bug it was framed as.
~~the `learning_input_<session>.json` payload files are never cleaned up if
`extract_skills.py` crashes before deleting them.~~

### ✅ M9. `cli.py:run_domain_refresh_with_sync` triple-imports json under three names
**RESOLVED (2026-06-14):** dropped the `import json as _json` / `import json as _jmod` / local
`import json` re-imports; all three sites now use the module-level `json`. (The function still
does too much — see H1 — but the import smell is gone.)

### ✅ M10. `evaluate_artifacts` computes `active_designs` but never returns them used
**RESOLVED (2026-06-15):** decided **remove** (always-empty field shown to the agent every
prompt). Stripped the `missing_documents` plumbing across dispatcher → classifier →
context_builder, including the `build_context` param, the SYSTEM STATE line, and the matching
"Artifacts Missing" line in the classifier's degraded fallback. Tests pin the field's absence.
(`designs_found`/`active_designs` left as-is — separate field, out of scope.)
Read-side contract was already fixed by C2.
`dispatcher.py:300-312` scans `docs/designs` and `docs/progress`, but only `manifest_state`
carries them and `context_builder` only renders `progress_found` (B branch). `designs_found`
is rendered only by the classifier's *degraded* fallback path. Also `missing_documents` is
always `[]` — the whole "Missing Documents" feature is vestigial. Either implement it or
remove the plumbing.

## LOW

- ✅ **RESOLVED (2026-06-14):** `adapters/__init__.py:get_builder/get_runtime_adapter` now
  `raise TypeError(...)` instead of `assert isinstance(...)` — survives `python -O`.
- `profile.py` docstring says "ZERO harness.* imports … copied standalone (S2-T6)" — true, but
  `runtime_adapter.py` imports it as `harness.adapters.profile`; the doc usage example shows
  the harness-package import. Fine, just keep the claim precise.
- `notify_compression.py` prints `systemMessage` — Claude-only field; harmless elsewhere.
- `merge_structured` returns `yaml.dump(..., sort_keys=False)` — round-trips comments away
  (operators' comments in features.yaml are lost on re-mint merge). Document or move to
  ruamel if comment preservation matters.
- `langfuse_compat.update_current_trace` stuffs `session_id`/`tags` into metadata — v4 has
  first-class `update_current_trace(session_id=…)` on recent SDKs; revisit when bumping.
- ✅ **RESOLVED (2026-06-14):** `_missing_verdict(cls)` in `updater.py` inlined to the literal
  `"restore-missing"`; the placeholder function is deleted.
- 8 ruff F541 f-strings without placeholders; 7 E402 module-import-not-at-top.
- Naming: `harness_features_tree.md` at repo root vs `docs/` for everything else.

---

## Redundant / unused — deletion candidates (summary)

| Item | Where | Action |
|---|---|---|
| ✅ `generate_orchestrator_plugin` import | `adapters/claude.py:7` | **DONE** — deleted (lazy-import workaround left in place) |
| ✅ `acquire_mcp_context`, `fetch_skill`, `fetch_remote_skill`, dup `TemplateRenderer` | `init/discovery_engine.py` | **DONE** — module deleted, dropped from `RUNTIME_FILE_MAP`, tests repointed (H6) |
| Claude copy of `format_hook_response` | `adapters/claude.py:227-276` | Replace with delegation to `RuntimeAdapter("claude")` |
| 4× placeholder-rewrite loops | gemini/codex/cursor/claude adapters | Extract shared helper |
| ✅ 3× platform digit maps + if/elif folder map | `cli.py`, `minting_engine.py` ×2 | **DONE** — extracted `init/platforms.py` (H4) |
| ✅ Dead validate-retry branch | `cli.py:159-168` | **DONE** — deleted (C3) |
| ✅ 29 unused imports / 6 redefinitions | repo-wide (ruff list) | **DONE** — cleared (M1, pyflakes-verified) |
| `S2-T3/T4` back-compat shims (`generate_core_infrastructure`) | `base.py`, claude, gemini | Finish migration, delete shim |
| ✅ Stale `__pycache__` for deleted modules; boilerplate `state/*.json` | filesystem | **DONE** — cleaned (H9) |
| ✅ Stale codegraph index (listed deleted `ghost.py`) | `.codegraph/` | **DONE (local)** — `index --force` + exclude mirror/benchmark, 347→225 files (H8) |
| ✅ `missing_documents` plumbing (always `[]`) | dispatcher → context_builder → classifier | **DONE** — removed (M10) |
| ✅ Redundant `(UnicodeDecodeError, Exception)` tuple | `init/minting_engine.py:363` | **DONE** — collapsed (M4) |
| ✅ `_missing_verdict` placeholder fn | `update/updater.py` | **DONE** — inlined + deleted (LOW) |
| ✅ Triple `json` re-import | `cli.py:run_domain_refresh_with_sync` | **DONE** — collapsed to module-level (M9) |
| ✅ Tautological `assert isinstance` | `adapters/__init__.py` | **DONE** — now `raise TypeError` (LOW) |

## Suggested fix order

1. ✅ **C1–C4** (routing latency, contract-mismatch keys, dead validator retry, unbounded log) — **DONE 2026-06-14**.
2. ✅ **H5 + H6 + M1** (delete unused import/module, ruff --fix) — **DONE 2026-06-14** (H5 + M1 + H9 + H6). H6 turned out non-trivial (test surface), executed carefully with an offline gate.
3. ✅ **Easy correctness/cleanup batch** (M4, M6, M9, M7-docstrings, asserts, `_missing_verdict`) — **DONE 2026-06-14**, TDD test for M6, unit (1013) + integration (50) green. H8 "36 files" retracted.
4. ✅ **H4 + M10 + H8** (digit-map dedup, remove missing_documents, codegraph clean-rebuild) — **DONE 2026-06-15**, TDD for H4/M10, unit+integration 1076 / e2e+hooks 317 green.
5. **H2 + H3** (de-duplicate adapter logic) — guarded by the existing byte-identity tests.
6. **H7** (generic parity); optionally wire codegraph `mark-dirty`/`sync-if-dirty` hooks.
7. **H1 + M2** (cli.py decomposition) — biggest refactor, do last with the e2e mint tests green.
