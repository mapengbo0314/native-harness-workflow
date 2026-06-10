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

- Project-ops manifest (`domain.json`) + `domain` MCP server exposing the
  single pull tool `domain_ops(topic)`: `domain-init` (stack detection via
  GitHub Linguist + cdxgen, offline fallback; never clobbers authored
  content), `domain-compile` (LLM-distilled `business` section from
  `docs/reference/`), `domain-refresh` (re-detect + merge). Registered on
  claude/gemini/cursor/codex mints; `init` prints the two-step
  docs-then-compile guidance. The `business` digest is injected on
  planning/question branches.
- Native codex and cursor platform support (AGENTS.md manifests, corrected
  hook schemas/event mappings, honest crash fallbacks) and a platform
  support matrix (`docs/platform-support.md`).
- Optional RTK shell-output compression (`--rtk` / `--install-rtk`).
- harness-bench (`clawbench_v2`) benchmark foundation + SWE-bench Lite tasks.
- Ownership manifest (`.harness-meta.json` `owned` map) and the read-only
  `harness-wf update --check` planner: two-hash detection (template-space
  "did we change it" + rendered-space "did the user edit it"), real 3-way
  merge via `git merge-file`, gzipped base sidecar for customizable files,
  and ghost-injection split for `implementer.md`. (Phase A of the
  2026-06-01 update design.)

### Changed

- `plugin.json` version is stamped from `pyproject.toml`; build metadata
  lives in `.harness-meta.json` (PR #26).

### Fixed

- Langfuse v4 compatibility: the no-credentials guard now also sets
  `LANGFUSE_TRACING_ENABLED=false` (the v3+/v4 kill-switch), silencing
  auth-warning noise on credential-less runs; test subprocesses scrub
  Langfuse credentials entirely so test prompts can never export traces.
- A failed/unparseable `domain-compile` no longer wipes a previously
  compiled `business` section.

## [0.1.0]

- Initial harness minting CLI (`harness-wf init`): platform adapters,
  orchestrator plugin generation, hooks, skills, agents, CodeGraph onboarding.
