# Changelog

All notable changes to `harness-wf` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with **intent** (see `docs/RELEASING.md`):

- **PATCH** — runtime/hook bugfix; safe to overwrite on update.
- **MINOR** — additive skills/agents/features; merged on update.
- **MAJOR** — manifest/contract break; ships a migration, blocks piecemeal update.

## [Unreleased]

### Added
- Ownership manifest (`.harness-meta.json` `owned` map) and the read-only
  `harness-wf update --check` planner: two-hash detection (template-space
  "did we change it" + rendered-space "did the user edit it"), real 3-way
  merge via `git merge-file`, gzipped base sidecar for customizable files,
  and ghost-injection split for `implementer.md`. (Phase A of the
  2026-06-01 update design.)

### Changed
- `plugin.json` version is stamped from `pyproject.toml`; build metadata
  lives in `.harness-meta.json` (PR #26).

## [0.1.0]
- Initial harness minting CLI (`harness-wf init`): platform adapters,
  orchestrator plugin generation, hooks, skills, agents, CodeGraph onboarding.
