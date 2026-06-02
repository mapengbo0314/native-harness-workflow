# Harness Update & Releases — Progress

Design: `2026-06-01-harness-update-and-releases-design.md` (incl. reworked Resolutions R1–R11).
Status legend: [ ] todo · [~] in progress · [x] done
Readiness legend: 🟢 ready now (pure / read-only, no unknowns) · 🟡 light refactor needed · 🔴 blocked on a refactor decision

---

## Phase A — Detection foundation (🟢 READY NOW — read-only, mutates nothing)

Goal: ship `harness-wf update --check` (dry-run) end-to-end. No file in `.claude/` is ever written by this phase.

- [x] A1. 🟢 `tests/unit/test_update_classification.py` → `src/harness/update/classification.py` (DONE) — glob→class (`generated`/`customizable`/`derived`), `producer` tags, EXCLUDE set; user paths + pollution NOT owned.
- [x] A2. 🟢 normalize+hash helper in `manifest.py` → `tests/unit/test_update_manifest.py` (DONE)
- [x] A3. 🟢 `manifest.write_manifest` / `read_manifest` (standalone) → `tests/unit/test_update_manifest.py` (DONE; real-mint wiring is C1)
- [x] A4. 🟢 `updater.plan_update` two-hash truth table → `tests/unit/test_update_updater.py` (DONE)
- [x] A5. 🟢 `conflict.three_way` over `git merge-file -p` → `tests/unit/test_update_merge3.py` (DONE)
- [x] A6. 🟢 base sidecar writer/reader in `manifest.py` → `tests/unit/test_update_sidecar.py` (DONE)
- [x] A7. 🟢 `harness-wf update --check` (read-only) in `cli.py` → `tests/integration/test_update_check.py` (DONE)

## Phase B — Producer reproduction (🔴/🟡 REFACTOR FIRST — gates all apply)

Goal: given a new package, reproduce the correct "theirs" bytes per `producer`. Decisions locked: D1 refactor+characterization, D2 replicate quirks exactly, D6 owned-roots allow-list, distribution=PyPI, edge files (ignore docs/, orchestrator-if-present).

- [x] B0. 🟡 **Relocate `agent.json`, `skills.json`, AND `rules/` into the plugin** — DONE (commits 479322c, aab59cb; assemble*layout payload + dispatcher pointer + export_rules path + classification + relocation test; 448 passing) (`harness-wf-plugin/`); add to `assemble_layout` payload; fix `dispatcher.py:243` pointer → `${CLAUDE_PLUGIN_ROOT}/skills.json`; point `export_rules_config` at `plugin/rules/`. Classify JSON generated/overwrite, `rules/*.md`customizable. **AGENTS.md stays external** (CLAUDE.md pointer). **Migration-worthy (MAJOR): migration removes old`.claude/`-root copies\*_ (full effect once apply/Phase C lands). Add dispatcher + export tests. \_Do B0 before B1 (it changes mint output)._
- [x] B1. DONE (commits 1a1e24a, a127bc6) — `src/harness/init/render.py` (`render_pass1`, `render_template`, moved `TemplateRenderer`+`process_includes`); mint Pass-1 calls `render_pass1`; 9 characterization tests; two-pass ordering preserved; 457 passing. Caveat: orchestrator injection now after render_pass1 (benign, snapshots unchanged; irrelevant to update's render_template). — was: Extract a **pure single-file render** from `mint_workspace` (Jinja + `.claude`→dir + tool_mappings + `@include`) callable as `render_template(src, context)` with NO side effects (no sentinel, no ghost injection, no CONTEXT.md seeding). **D3: lightweight render fixture + one e2e backstop**; characterize the **post-B0** layout byte-for-byte first (D2: replicate quirks incl. naive replace + silent Jinja-fail). Then refactor mint to CALL it (D1).
- [x] B2. DONE (commit 0d78360) — `src/harness/init/runtime_slice.py` (`RUNTIME_FILE_MAP`, `rewrite_imports`, `emit_platform_adapter`, `reproduce_runtime_file`); `copy_runtime_modules` refactored to use them; `classification.RUNTIME_SOURCE_MAP` derived from the shared map (D5); platform_adapter re-emit (D4); 524 passing.
- [x] B3. DONE (commit 2905e96) — `regenerate_derived(plugin_dir, harness_dir=None)` in `plugin_generator.py` orchestrates the existing `export_*` (no reimpl); skips absent orchestrator.md; `DERIVED_FROM` mapping (D8) in classification; desync-prevention + idempotency tests; 545 passing.
- [x] B4. 🟢 `implementer.md` split at marker → `src/harness/update/ghost.py`, `tests/unit/test_update_ghost.py` (DONE)

## Phase C — Transactional apply (after B)

- [x] C1. Wire `write_manifest` + `write_base_sidecar` into `cli.py` as the final post-swap init step; extend an init integration test (assert `owned` present, customizable bases present, pollution + `.env.telemetry-harness` excluded). DONE — init now stamps update metadata after final plugin layout exists; C1 spec + quality reviews approved.
- [x] C2. `conflict.py` interactive resolver K/O/D/M; EOF/KeyboardInterrupt → clean abort; headless path. DONE — resolver + tests pass; quality review found editor-invocation edge, fixed with invalid-editor retry + editor-time KeyboardInterrupt abort. Final review approved.
- [x] C3. `updater.apply_update` five-phase: plan → resolve(all up front) → stage (derived regen from STAGED md) → journal+commit (`os.replace`, backups) → cleanup. Manifest stamped last. Include minimal R9/R10 safety gates here: same-MAJOR only, headless fail-closed on `requires_human`, no partial apply. DONE — apply engine + CLI wiring + focused tests pass; first spec review found metadata journaling gap, fixed by staging manifest/base sidecars and committing them through the journal; final quality review found stale version stamping, fixed so manifest stamps the installed package version. Final review approved.
- [x] C4. Startup **journal recovery** (R8): on `update`/`init` start, restore from `backup/` if `.harness-update-journal.json` present. Test crash-mid-commit → recovered pre-update state. DONE — recovery runs at update/init start and unit coverage restores payload/new files/manifest metadata. Final review approved.
- [x] C5. Source-driven planning (R7) + missing-file policy: discover new upstream harness producer-paths as new owned files; detect removed upstream files; separately detect local missing files from the old manifest. User files remain invisible because only known producer-paths are considered. Policy: generated local-missing → restore from upstream; customizable local-missing → human/headless-stop; derived local-missing → regenerate from current/staged sources. DONE — planner now unions manifest entries with current source producers, detects collisions as `requires-human`, preserves `removed-upstream`, and splits local-missing verdicts by class; spec + quality reviews approved.
- [x] C6. Emitted Claude manifest handling: update only the harness-owned references in `.claude-plugin/plugin.json` / `.claude-plugin/marketplace.json` (append/replace the harness entry), preserving unrelated Claude-managed content. DONE — plugin.json preserves unrelated fields; marketplace updates/replaces only the orchestrator-plugin entry and preserves top-level marketplace metadata. Final review approved.
- [x] C7. `tests/integration/test_update_apply.py` E2E: edit a generated file, a clean customizable file, a conflicting customizable file → `update` → assert refresh, edits preserved, conflict path, derived JSON matches merged md, AND a hand-placed `.claude/settings.json` + custom skill are byte-identical after. DONE — integration coverage added in `tests/integration/test_update_check.py`; focused Phase C suite passed 83 tests. Final review approved.

### Phase C Pending

- [x] Final spec re-review after fixes for C2/C3/C4/C6/C7.
- [x] Final code-quality review after spec re-review passes.
- [x] If approved, mark C2/C3/C4/C6/C7 `[x]` and run the final Phase C focused suite.

## Phase D — Major Upgrades & Force Modes (after safe apply)

- [x] D1. Major Upgrades: structural updates across MAJOR boundaries via `--force-major`. No complex migration framework; rely on manifest additions/removals. (Includes targeted cleanup for B0 orphaned paths if necessary).
- [x] D2. `--force` / `--force-major`: rename `--overwrite-keep-yours` to `--force` (take-theirs for conflicts), still atomic, and require explicit major intent.
- [x] D3. `--adopt` mode: synthesize manifest for pre-manifest mints using installed package templates as `source_hash` and local disk as `rendered_hash` (forces `keep-yours` on user edits).
- [x] D4. Path Relocations: pre-planner migration for moved paths (e.g., B0 `rules/` and `*.json` moves). Move the physical file to its new location before planning so existing `rendered_hash` state and user edits are preserved for the 3-way merge.

## Slice 2 — Release discipline (parallelizable; mostly process)

- [x] S1. 🟢 `tests/unit/test_update_version_stamp.py` — manifest version == pyproject version (DONE)
- [x] S2. 🟢 `CHANGELOG.md` + `docs/RELEASING.md` (DONE)
- [ ] S3. Tag `v0.2.0` after Phase A–C land.

---

## Notes

- Prerequisite PR #26 (semver stamp → `.harness-meta.json`) merged to main 2026-06-01.
- **Recommended first deliverable: Phase A (`update --check`)** — fully ready, zero mutation, useful alone.
- **First real decision: B1** (extract pure single-file render). Apply is blocked on it.
- Hard constraint: `update` only touches files matching harness producer-paths; user files stay invisible (R7).
- Conflict policy: report + interactive CLI (K/O/D/M); headless = fail-closed (R10). Real 3-way via `git merge-file`, NOT lossy `merge_markdown`.
- `derived` class (R2) regenerates agents.json/rules.json from merged `.md` — removes the `.md`↔`.json`↔dispatcher desync and most of the old contract-group concern.

## Review / Query Checklist

- [x] Severity taxonomy
- [x] Impact / Regression
- [x] Reproducibility
- [x] Confidence

## Severity Levels of Issues

- [Critical] None
- [High] None
- [Medium] None
- [Low] None

## Findings

- ✅ Spec compliant: D1 and D2 features were implemented flawlessly.
- `--force-major` and `--force` CLI args correctly mapped and plumbed to the updater core.
- Missing upstream files with `customizable` properly blocked without `--force`.
- `_ensure_same_major` correctly blocks unforced cross-major updates.
- Tests (e.g., `test_plan_update_force`) were correctly renamed and pass.

## Current Blockers

- **`update --check` Broken for B0 Migration (Critical)**: `src/harness/init/cli.py` ignores `_migrate_b0_paths(dry_run=True)` during dry-runs. This causes `update --check` to produce a completely wrong plan (showing migrated files as missing/new) because `plan_update` evaluates against the old un-migrated manifest.

### Structured Review Checklist

- [x] Severity taxonomy
- [x] Impact / Regression
- [x] Reproducibility
- [x] Confidence

#### Findings

- [Critical] [src/harness/init/cli.py] [CLI/UX] `update --check` completely skips `_migrate_b0_paths` for dry runs. This causes the pre-planner migration to be ignored, meaning `plan_update` evaluates against the old un-migrated manifest. `cli.py` line 272 must read the manifest, call `_migrate_b0_paths` with `dry_run=True`, and then pass the updated manifest to `plan_update`.
- [Minor] [src/harness/update/updater.py] [Architecture] `_migrate_b0_paths` properly stages moved files into the manifest dictionary so `plan_update` processes them, but the final manifest writes them using a fresh evaluation against `staged_plugin`. This achieves the requirement but relies on overlapping state updates.
