# Releasing `harness-wf`

The harness has **two version planes** (see the 2026-06-01 update design). This
doc covers the *tool* plane — how we cut releases that deployed harnesses can
update against.

```
TOOL plane  (this repo)                 DEPLOYED plane (a target project)
harness-wf package                      .claude/harness-wf-plugin/
version = pyproject.toml                version = .harness-meta.json
released by: git tag + (git-ref/PyPI)   updated by: harness-wf update
```

## SemVer with intent

The version bump is a **contract signal** the `update` command reads, not just
a number:

| Bump | Meaning | `update` behavior |
|------|---------|-------------------|
| PATCH (`0.1.0→0.1.1`) | runtime/hook bugfix, no contract change | generated files overwrite freely |
| MINOR (`0.1.0→0.2.0`) | additive skills/agents/features | customizable files 3-way merged |
| MAJOR (`0.1.0→1.0.0`) | manifest/contract break (e.g. dir rename, schema change) | piecemeal update refused; ships a migration or requires re-mint |

The `harness-wr-plugin → harness-wf-plugin` rename is the canonical example of a
change that *should* be a MAJOR with a migration step.

## Cutting a release

1. Update `CHANGELOG.md`: move `[Unreleased]` items under a new `[X.Y.Z]` heading.
2. Bump `version` in `pyproject.toml` (single source of truth; stamped into
   `.harness-meta.json` at mint).
3. Commit, then tag: `git tag vX.Y.Z && git push --tags`.
4. Distribute via **PyPI** (primary): `uv build && uv publish`; consumers
   `uv tool install harness-wf`. A tag without a corresponding PyPI release is
   not a real release. (Source of truth is `main` + the SemVer tag; PyPI is the
   distribution channel.)

## Updating a deployed harness (two steps)

```
uv tool upgrade harness-wf          # tool plane: get new templates/runtime from PyPI
harness-wf update --project-path .  # deployed plane: apply, manifest-scoped
```

`harness-wf update --check` previews verdicts (stale/edited/conflicting) and
writes nothing. A MAJOR step or any conflict makes the run require a human
(fails closed in headless/CI).

## Invariant

A deployed `.harness-meta.json` always records the exact tool version that
produced it, so `update` can compute the version step and gate accordingly.
A test (`tests/unit/test_update_version_stamp.py`) locks manifest version to
`pyproject.toml`.
