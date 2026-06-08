---
Status: In Progress
Created: 2026-06-07
Design: 2026-06-07-domain-ops-manifest-design.md
---

# Progress — Domain-as-Project-Ops Manifest

Fresh branch `feat/domain-ops-manifest` off `main`. Strict TDD (failing test
first). One clean commit per phase. The abandoned DDD work lives on
`feat/domain-model-design` (not merged).

## Completed
- [x] Phase 0 — Docs: design + this progress checklist.

## Phase 1 — Model + MCP
- [ ] `tests/unit/test_domain_model.py` (OpsManifest: 7 topics incl. business, topic(), blank-drop list-aware)
- [ ] `src/harness/domain/model.py`
- [ ] `tests/unit/test_domain_server.py` (domain_ops; find_manifest_path → DOMAIN_JSON_PATH / `<plugin>/domain/domain.json`)
- [ ] `src/harness/domain/server.py`

## Phase 2 — Detectors
- [ ] `tests/unit/test_domain_detect.py` (languages via GitHub API mocked + extension fallback; cdxgen frameworks/services mocked; cdxgen-failure degradation)
- [ ] `src/harness/domain/detect.py`

## Phase 3 — Seed / init (scaffold)
- [ ] `tests/unit/test_domain_seed.py` (detect stack; scaffold env/test/deploy/infra slots; references manual; write plugin path; scaffold `.claude/docs/reference/`)
- [ ] `src/harness/domain/seed.py`
- [ ] `tests/unit/test_cli_domain.py` (domain-init routing + init scaffold)
- [ ] `src/harness/init/cli.py` wiring

## Phase 4 — Compile (author → business)
- [ ] `tests/unit/test_domain_compiler.py` (read `.claude/docs/reference/`; bound input + map-reduce; draft-approval; write plugin path; fake query_llm_fn)
- [ ] `src/harness/domain/compiler.py`
- [ ] `domain-compile` CLI routing

## Phase 5 — Consume (push business digest)
- [ ] `tests/unit/test_context_builder_business.py` (B/C only; absent A/D/E; empty omitted; render cap)
- [ ] `src/harness/runtime/context_builder.py`
- [ ] `src/harness/runtime/dispatcher.py` (load manifest → pass business)

## Phase 6 — Update-safety + registration + deploy
- [ ] `tests/unit/test_classification_domain_ownership.py` (domain/** user-owned; update + re-mint preserve)
- [ ] `src/harness/update/classification.py`
- [ ] `src/harness/adapters/claude.py` + `.mcp.json` (DOMAIN_JSON_PATH)
- [ ] `src/harness/init/runtime_slice.py` (deploy model.py + server.py)
- [ ] `src/harness/init/minting_engine.py` + `CLAUDE.md` (domain_ops pointer)

## Phase 7 — Dogfood + close
- [ ] `docs/domain/domain.schema.md`
- [ ] author this repo's `.claude/docs/reference/`; run compile; populate `<plugin>/domain/domain.json`
- [ ] full unit+integration suite green
- [ ] update platform snapshots if CLAUDE.md pointer changed

## Blockers
(none)
