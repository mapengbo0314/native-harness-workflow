---
Status: Completed
Created: 2026-06-07
Design: 2026-06-07-domain-ops-manifest-design.md
---

# Progress — Domain-as-Project-Ops Manifest

Fresh branch `feat/domain-ops-manifest` off `main`. Strict TDD. The abandoned DDD
work lives on `feat/domain-model-design` (not merged). **All phases complete;
full unit+integration suite green (725 passed).**

## Completed
- [x] Phase 0 — Docs: design + progress checklist.
- [x] Phase 1 — Model + MCP (`model.py`, `server.py`; 49 tests). Reviewed inline (spec ✅, dropped unused `_BLANK`).
- [x] Phase 2 — Detectors (`detect.py`: GitHub Linguist `/languages` + extension fallback; cdxgen frameworks/services; graceful degradation).
- [x] Phase 3 — Seed/init (`seed.py`: detect stack + scaffold empty slots + `.claude/docs/reference/`; never clobbers existing manifest).
- [x] Phase 4 — Compile (`compiler.py`: read `.claude/docs/reference/`, bounded input, isolated local-CLI LLM, merge `business`, no API key).
- [x] Phase 5 — Consume (`context_builder` injects capped `business` digest on B/C; `prompt_classifier` loads it, flat-import only).
- [x] Phase 6 — Wiring/deploy (CLI `domain-init`/`domain-compile` + init scaffold; `runtime_slice` deploys model+server + `domain` rewrite; `.mcp.json` + `adapters/claude.py` register domain MCP w/ `DOMAIN_JSON_PATH`; CLAUDE.md pointer; classification locks `domain/**` user-owned).
- [x] Phase 7 — Dogfood + docs (`docs/domain/domain.schema.md`; repo `domain.json` + `.claude/docs/reference/README.md`; snapshots regenerated; full suite green).

## Deferred / follow-ups (noted, not blocking)
- Compile input scaling uses per-doc + total cap with truncation; full **map-reduce** (per-doc summarize → merge) deferred until a real large-docs case needs it.
- `adapters/claude.py` domain MCP registration is wired but **not runtime-verified** in a live minted project this session (needs an end-to-end `harness-wf init` smoke test).
- Optional **draft-approval** before writing `business` not implemented (writes directly; hand-editable after). 
- ~~The planning JIT line in `context_builder` still says "DDD / ubiquitous language"~~ — **resolved**: removed the planning DDD JIT line, dropped the `## Ubiquitous Language` CONTEXT.md scaffold, and retired the entire old DDD/onboarding cluster from `discovery_engine.py` (`discover_agents`, `deep_audit_discovery`, `detect_tech_stack`, `generate_onboarding_domain_doc`, `generate_grilling_questions`, `synthesize_grilled_context` + `get_symbol_census`/`get_file_tree_summary` helpers). `run_debug.py` repointed to `domain.detect.detect_stack`. Obsolete tests removed; suite green (884 passed).
- `business` not yet populated for this repo (needs `harness-wf domain-compile` with a local CLI + authored `.claude/docs/reference/` docs).

## Blockers
(none)
