# `domain.json` schema

The project-ops manifest: the operational + product facts an agent can't reliably
derive from source. Lives at **`<plugin>/domain/domain.json`** (e.g.
`.claude/harness-wf-plugin/domain/domain.json`) — user-owned; `harness-wf update`
never touches it. Pulled on demand via the `domain` MCP's `domain_ops(topic)`
tool; the small `business` digest is also pushed into context on planning (B) and
question (C) turns.

## Top-level

| Key | Type | Source | Purpose |
|---|---|---|---|
| `schema_version` | int | — | Schema version (currently `1`). |
| `stack` | list[str] | **detected** | Languages (GitHub Linguist) + frameworks (cdxgen). |
| `environments` | object | **manual** | How to run/build per env (`local`, `sandbox`, `uat`, …). |
| `test` | object | **manual** | Test/lint commands (`unit`, `integration`, `lint`, …). |
| `deploy` | object | **manual** | How to ship (`command`, `rollback`, …). |
| `infra` | object | **manual** | Container/k8s/other (`container`, `k8s`, `notes`, …). |
| `references` | object | **suggested + manual** | Doc path → one-line why-it-matters; agent reads on demand. |
| `business` | object | **LLM-compiled** | `direction`, `priorities`, `constraints`, `non_goals`. |

Blank/empty values are dropped on load; non-empty lists are kept. `_comment` (if
present) is ignored by the model.

## How each part is produced

- **`stack`** — `harness-wf domain-init` runs detection: GitHub Linguist via the
  `/languages` API (weighted; file-extension fallback offline) + cdxgen (`npx`)
  for frameworks and services. No code-structure inference.
- **`environments` / `test` / `deploy` / `infra`** — scaffolded as empty slots by
  `domain-init`; engineers fill the facts only they know.
- **`references`** — `domain-init` pre-suggests conventional docs (path → first
  H1); humans curate.
- **`business`** — `harness-wf domain-compile` reads `.claude/docs/reference/`
  (human-authored PRD/product docs) and makes ONE isolated LLM call (the local
  `claude`/`gemini` CLI — **no API key**) to distill the four fixed fields. It is
  a point-in-time digest: re-run when the docs change. The LLM only summarizes
  human-authored docs; it never reads code.

## Retrieval / delivery

- `domain_ops(topic)` — `topic` ∈ `stack | environments | test | deploy | infra |
  references | business | all`. Returns just that slice (pull on demand).
- `build_context` injects the small `business` digest into the `=== SYSTEM STATE
  ===` block on branches **B** and **C** only, with a render cap.

## The flow

```
detect (stack)  →  scaffold (slots + docs/reference/)  →  author (engineers fill
slots, drop docs)  →  compile (LLM → business)  →  consume (domain_ops pull +
business push on B/C)
```

`domain.json` is hand-editable — every field can be corrected directly; detection
and the LLM only produce a draft.
