# Harness Update & Releases — Progress

Design: `2026-06-01-harness-update-and-releases-design.md` (incl. reworked Resolutions R1–R11).
Status legend: [ ] todo · [~] in progress · [x] done
Readiness legend: 🟢 ready now (pure / read-only, no unknowns) · 🟡 light refactor needed · 🔴 blocked on a refactor decision

---

## Phase A — Detection foundation (🟢 READY NOW — read-only, mutates nothing)
Goal: ship `harness-wf update --check` (dry-run) end-to-end. No file in `.claude/` is ever written by this phase.

- [ ] A1. 🟢 `tests/unit/test_classification.py` → `src/harness/update/classification.py`
      glob→class (`generated`/`customizable`/`derived`), `producer` tag (`template`/`runtime_copy`/`export`/`verbatim`), EXCLUDE set (`state/`,`logs/`,`.venv/`,`.deepeval/`,`__pycache__/`,`*.pyc`,`harness.db`,`uv.lock`,`.env.telemetry-harness`). Assert user paths + pollution are NOT owned.
- [ ] A2. 🟢 `tests/unit/test_hashing.py` → normalize+hash helper (LF, strip trailing WS) in `manifest.py`. Pure.
- [ ] A3. 🟢 `tests/unit/test_manifest.py` → `manifest.write_manifest` / `read_manifest`. Records `source_hash`, `rendered_hash`, `class`, `producer`, `source_path`; excludes EXCLUDE set; version from pyproject. (Write is wired into mint in Phase C; here test it standalone against a fixture tree.)
- [ ] A4. 🟢 `tests/unit/test_updater_plan.py` → `updater.plan_update` two-hash truth table (we_changed × user_edited → current/apply/keep-yours/CONFLICT). Verdict-only, no disk. Parametrized.
- [ ] A5. 🟢 `tests/unit/test_merge3.py` → `conflict.three_way(ours, base, theirs)` wrapper over `git merge-file -p`. Returns merged text + conflict flag. Pure, fixture-driven.
- [ ] A6. 🟢 `tests/unit/test_base_sidecar.py` → base sidecar writer (gzip customizable files). Pure.
- [ ] A7. 🟢 `tests/integration/test_update_check.py` → `harness-wf update --project-path . --check` reads manifest, prints verdicts, **writes nothing**. Assert exit code + zero disk mutation.

## Phase B — Producer reproduction (🔴/🟡 REFACTOR FIRST — gates all apply)
Goal: given a new package, reproduce the correct "theirs" bytes per `producer`. This is the real first decision.

- [ ] B1. 🔴 Extract a **pure single-file render** from `mint_workspace` (Jinja + `.claude`→dir + tool_mappings + `@include`) callable as `render_template(src, context)` with NO side effects (no sentinel, no ghost injection, no CONTEXT.md seeding). Characterization tests first to pin current output byte-for-byte.
- [ ] B2. 🟡 `runtime_copy` reproduction: factor `copy_runtime_modules` so a single runtime artifact (incl. emitted `platform_adapter.py`) can be reproduced for compare/apply.
- [ ] B3. 🟡 `derived` regeneration: make `export_orchestrator_config`/`export_agents_config`/`export_rules_config` regenerate JSON from an arbitrary (staged) `.md` dir → config dir.
- [ ] B4. 🟢 `implementer.md` split at exact marker `### STRICT INVARIANTS (Ghost Injection)` — harness owns above, project owns below (R4). Small/pure.

## Phase C — Transactional apply (after B)
- [ ] C1. Wire `write_manifest` into `cli.py` as the final post-swap init step; extend an init integration test (assert `owned` present, pollution + `.env.telemetry-harness` excluded).
- [ ] C2. `conflict.py` interactive resolver K/O/D/M; EOF/KeyboardInterrupt → clean abort; headless path.
- [ ] C3. `updater.apply_update` five-phase: plan → resolve(all up front) → stage (derived regen from STAGED md) → journal+commit (`os.replace`, backups) → cleanup. Manifest stamped last.
- [ ] C4. Startup **journal recovery** (R8): on `update`/`init` start, restore from `backup/` if `.harness-update-journal.json` present. Test crash-mid-commit → recovered pre-update state.
- [ ] C5. `tests/integration/test_update_apply.py` E2E: edit a generated file, a clean customizable file, a conflicting customizable file → `update` → assert refresh, edits preserved, conflict path, derived JSON matches merged md, AND a hand-placed `.claude/settings.json` + custom skill are byte-identical after.

## Phase D — Headless gates & version semantics (R9–R11)
- [ ] D1. SemVer parse + step classifier (patch/minor/major) from deployed `.harness-meta.json` vs installed pyproject.
- [ ] D2. `requires_human` (R10): any CONFLICT · customizable-remove · cross-MAJOR · absent/unparseable version · missing manifest. Headless → print + apply nothing + exit non-zero.
- [ ] D3. Cross-MAJOR gate (R9): refuse piecemeal; require migration or re-mint. `--force` (take-theirs, atomic) + `--force-major` + `--adopt` (synthesize manifest from current tree).

## Slice 2 — Release discipline (parallelizable; mostly process)
- [ ] S1. 🟢 `tests/unit/test_version_stamp.py` — `.harness-meta.json` version == pyproject version.
- [ ] S2. 🟢 `CHANGELOG.md` (Keep-a-Changelog) + `docs/RELEASING.md` (tag → SemVer-intent → git-ref/PyPI).
- [ ] S3. Tag `v0.2.0` after Phase A–C land.

---

## Notes
- Prerequisite PR #26 (semver stamp → `.harness-meta.json`) merged to main 2026-06-01.
- **Recommended first deliverable: Phase A (`update --check`)** — fully ready, zero mutation, useful alone.
- **First real decision: B1** (extract pure single-file render). Apply is blocked on it.
- Hard constraint: `update` only touches files matching harness producer-paths; user files stay invisible (R7).
- Conflict policy: report + interactive CLI (K/O/D/M); headless = fail-closed (R10). Real 3-way via `git merge-file`, NOT lossy `merge_markdown`.
- `derived` class (R2) regenerates agents.json/rules.json from merged `.md` — removes the `.md`↔`.json`↔dispatcher desync and most of the old contract-group concern.
