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

## Increment 3 — Interactive curses `features toggle`  ⬜ TODO
- [ ] 3.1 `build_checklist(data) -> list[(key, label, is_on)]` — pure view-model from data + `KNOWN_KEYS`
- [ ] 3.2 `toggle_at(data, index) -> data` — maps row → key, calls `apply_toggle` (pure)
- [ ] 3.3 Non-TTY guard — `features toggle` without a terminal falls back to `features list` + message (CI-safe)
- [ ] 3.4 Thin curses render/loop shell (logic-free; calls pure fns + `compile_features` on save); wire `features toggle`

## Increment 4 — Breadth: agents, hooks, MCPs  ⬜ TODO
- [ ] 4.1 `agents.*` in `KNOWN_KEYS`; `effective_agent(agent, root) -> @generalist` fallback; wire into dispatcher/classifier
- [ ] 4.2 `hooks.*` in `KNOWN_KEYS`; each hook early-exits on its flag
      (extend `session_end`/`post_tool_use`/`notify_compression`); guard the pipeline-killing hooks
- [ ] 4.3 `mcp.*` in `KNOWN_KEYS`; `compile_mcp_config` generates `.mcp.json` from flags at sync/mint
- [ ] 4.4 Fold `BRANCH_ROUTING` into `DEPENDENCIES` (branch→agent, branch→skill edges) so cascade spans classes
- [ ] 4.5 Add new blocks to template `features.yaml`; reconcile `harness_features_tree.md`

## Increment 5 — Delivery & integration  ⬜ TODO
- [ ] 5.1 Ownership entries in `src/harness/update/classification.py` for new generated files
      (`.mcp.json`, regenerated `settings.json`)
- [ ] 5.2 Verify mint/update auto-sync end-to-end; full suite green; `harness-wf update --check` merges cleanly

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
