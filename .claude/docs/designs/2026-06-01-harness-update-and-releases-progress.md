# Harness Update & Releases — Progress

Design: `2026-06-01-harness-update-and-releases-design.md`
Status legend: [ ] todo · [~] in progress · [x] done

## Slice 1 — Ownership manifest + `update` command
- [ ] T1. `test_classification.py` → `src/harness/update/classification.py` (glob→class rules + EXCLUDE set)
- [ ] T2. `test_manifest.py` → `src/harness/update/manifest.py` (write_manifest / read_manifest, hashing)
- [ ] T3. Wire `write_manifest` into `cli.py` final init step; extend init integration test (assert `owned` present, pollution excluded)
- [ ] T4. `test_updater.py` → `updater.plan_update` (4-bucket truth table, verdict-only, no disk)
- [ ] T5. `test_conflict.py` → `src/harness/update/conflict.py` (K/O/D/M + headless auto-keep)
- [ ] T6. `updater.apply_update` (route conflicts → conflict.py; re-stamp manifest)
- [ ] T7. Add `update` subcommand to `cli.py`; `tests/integration/test_update_command.py` E2E (incl. settings.json + custom-skill untouched assertions)

## Slice 2 — Release discipline
- [ ] T8. `tests/unit/test_version_stamp.py` (manifest version == pyproject version)
- [ ] T9. `CHANGELOG.md` + `docs/RELEASING.md`; tag `v0.2.0` after Slice 1 lands

## Notes
- Prerequisite PR #26 (semver stamp → `.harness-meta.json`) merged to main 2026-06-01.
- Conflict policy: report + interactive CLI resolution (no silent auto-merge). Headless = auto-keep-yours + report list.
- Ownership constraint (hard): `update` may only touch files listed in the manifest `owned` map.
