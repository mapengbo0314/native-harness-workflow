# Plugin-Selector Feature Toggles — Progress

**Branch:** `feat/plugin-selector-toggles`
**Goal:** Extend the existing `features.yaml → sync → features.json → feature_enabled`
engine into a full "plugin selector": every capability (branches, agents, hooks,
MCPs, skills) is a real, enforced toggle; an operator can *view* what's on; and
toggling is cascade-aware so a disabled feature degrades gracefully instead of
breaking the rest.

**Method:** Incremental TDD — every step is one red→green slice with exact files.

**Status legend:** `[x]` done · `[ ]` todo

---

## Increment 0 — Cascade engine + branch schema  ✅ DONE
- [x] `apply_toggle(data, key, value)` cascade resolver in `src/harness/init/features.py`
      (immutable; disables dependents transitively; enables dependencies transitively)
- [x] `branches.*` added to `KNOWN_KEYS`
- [x] Tests in `tests/unit/test_features_loader.py` (6: branch schema + cascade + immutability)

## Increment 1 — Branch consumer (Plan A–E degradation)  ✅ DONE
- [x] `effective_branch(branch, plugin_root)` in `src/harness/templates/boilerplate/hooks/hook_common.py`
      (disabled branch → `"E"`; `"E"`/unknown never degraded; fail-open)
- [x] Wired into `src/harness/templates/boilerplate/hooks/prompt_classifier.py`
      (recompute routing on degrade so SYSTEM STATE reflects the branch that runs)
- [x] `branches:` block added to template `src/harness/templates/boilerplate/features.yaml`
- [x] `harness_features_tree.md` branches section (marked implemented)
- [x] Tests in `tests/hooks/test_feature_toggles.py` (5: passthrough/degrade/E-never/unknown)

## Increment 2 — CLI: see & toggle non-interactively  ✅ DONE
- [x] 2.1 `format_features_status(data) -> str` — pure `[x]`/`[ ]` formatter
      (`features.py`; tests in `tests/unit/test_cli_features_toggle.py`)
- [x] 2.2 `run_features_list(plugin_root)` reads `features.json` + prints; wired `features list` in `cli.py`
- [x] 2.3 `valid_feature_key(key)` + `known_feature_keys()` — validate against flattened `KNOWN_KEYS`
- [x] 2.4 `run_features_set(plugin_root, key, value)` — read yaml → `apply_toggle` → write yaml → `compile_features`
- [x] 2.5 Wired `features enable/disable <key>` subcommands (new `arg` positional) in `cli.py`
- [x] 2.6 Error paths — unknown key exits 1; missing `features.yaml` exits 1
- [x] Verified end-to-end through the real `harness-wf` binary in a temp dir (sync/list/disable/cascade/enable/unknown)

## Increment 3 — Interactive curses `features toggle`  ✅ DONE
- [x] 3.1 `build_checklist(data) -> list[(key, is_on)]` — pure view-model from data + `KNOWN_KEYS`
- [x] 3.2 `toggle_at(data, index) -> data` — maps row → key, calls `apply_toggle` (pure, immutable)
- [x] 3.3 Non-TTY guard — `features toggle` without a terminal falls back to `features list` + message (CI-safe)
- [x] 3.4 Thin curses render/loop shell (`_run_curses_toggle`, logic-free; pure fns + `compile_features` on save); wired `features toggle`
- [x] Verified non-TTY fallback end-to-end via the real `harness-wf` binary

## Increment 4 — Breadth: agents, hooks, MCPs  ✅ DONE
- [x] 4.1 `agents.*` in `KNOWN_KEYS`; `effective_agent(agent, root) -> @generalist` (hook_common); wired into prompt_classifier
- [x] 4.2 `hooks.*` in `KNOWN_KEYS`; `hook_enabled()` early-exit in `post_tool_use` + `notify_compression`
      (prompt_classifier/pre_tool_use schema-valid but intentionally NOT runtime-gated — pipeline/security-critical)
- [x] 4.3 `mcp.*` in `KNOWN_KEYS`; `filter_mcp_servers()` + `compile_mcp_config()` regenerate `.mcp.json` from the
      `mcp_servers.json` catalog on `features sync`/`enable`/`disable`/`toggle` (non-destructive; no-op without catalog)
- [x] 4.4 Cross-class `DEPENDENCIES` edges branch→agent (plan_a→debugger, plan_b→planner, plan_d→implementer); cascade spans classes
- [x] 4.5 Added agents/hooks/mcp blocks to template `features.yaml`; reconciled `harness_features_tree.md` sections 3/4/6
- [x] Verified e2e via real binary: mcp drop, agent→branch cascade, effective_agent/effective_branch/hook_enabled consumers
- Note: branch→skill edges deferred (DEPENDENCIES is one-dep-per-feature; branch→agent is the load-bearing edge)

## Increment 5 — Delivery & integration  ✅ DONE
- [x] 5.1 Ownership in `classification.py`: `.mcp.json` → EMITTED_GENERATED; `mcp_servers.json` →
      customizable/template (like `features.yaml`). Shipped boilerplate `mcp_servers.json` catalog.
- [x] 5.2 `compile_mcp_config` wired into `features sync` (update auto-syncs); `enumerate_source_producers`
      discovers the catalog on the real package; full suite 1458 passed. (`settings.json` regeneration not
      needed — pipeline hooks are ungated by design, see 4.2.)
- Note: a from-scratch `harness-wf update --check` smoke wasn't run (needs a fully minted+manifested
  workspace); the classification path it uses is covered by unit tests + the update test-suite.
- Note: `compile_mcp_config` writes `<plugin_root>/.mcp.json`; if the platform reads `.mcp.json` from the
  project root, an emit-location follow-up is needed for the MCP toggle to take effect live. mint-time
  `compile_mcp_config` deferred (would touch minting_engine.py, kept untouched this session).

---

## Delivery path (how a deployed plugin gets these features)
1. `harness-wf` tool is on the updated package (editable in this repo; else reinstall the tool —
   tool-plane code like `apply_toggle`/`KNOWN_KEYS` ships in the package, **not** via `update`).
2. `harness-wf update --check` → `harness-wf update` — 3-way merges template
   `features.yaml` (new blocks) + updated hooks into `.claude/harness-wf-plugin/`,
   preserving operator toggles (`features.yaml` is classified `customizable`/`template`).
3. `harness-wf features sync` (auto-runs on update) → recompiles `features.json`.
4. Edit `features.yaml` (or `features toggle`) → sync → harness reflects the selection.

## Notes / decisions
- `plan_e_answer` is the always-on terminal fallback; the consumer never degrades `"E"`.
- Cascade direction is driven entirely by `DEPENDENCIES` (single source of truth shared
  with the compile-time validator) — extend that map, not ad-hoc logic.
- Branch toggles are deliberately added to the template only once a consumer reads them
  (no dead toggles).
