# Domain setup — how it works

The **project-ops manifest** (`domain.json`) captures how *this specific repo*
actually works — the operational and product facts an agent can't reliably derive
from source. One file, filled from three sources, read at runtime by one MCP tool.

For the field-by-field schema, see [`domain.schema.md`](./domain.schema.md). This
page is the workflow overview.

## The artifact

`domain.json` lives at `.claude/harness-wf-plugin/domain/domain.json` (inside the
minted plugin; user-owned — `harness-wf update` never touches it). Seven sections,
each with a different origin:

| Section | Holds | Source |
|---|---|---|
| `stack` | languages + frameworks | **auto-detected** |
| `environments` | env URLs / config | human-authored |
| `test` | how to run tests | human-authored |
| `deploy` | deploy commands / targets | human-authored |
| `infra` | infra provider / services | human-authored |
| `references` | doc pointers (path → why) | auto-suggested, human-curated |
| `business` | direction, priorities, constraints, non-goals | **LLM-distilled** from docs |

Three kinds of content — **auto-detected** (`stack`), **LLM-distilled**
(`business`), **human-authored** (the ops sections) — and that split drives the
whole lifecycle: each command updates only its own kind and never clobbers the
others.

## Where the data comes from

1. **GitHub Linguist** → languages (weighted via the `/languages` API; offline
   file-extension fallback). `detect.detect_languages`.
2. **cdxgen** → frameworks (CycloneDX BOM). `detect.detect_frameworks`. cdxgen is
   run **transiently** to a temp dir and the BOM is discarded after the framework
   names are extracted — see "About `bom.json`" below.
3. **An LLM over `.claude/docs/reference/`** → the `business` digest. You drop
   PRDs / product-direction docs in that folder; `domain-compile` distills them.

`stack` = languages + frameworks, de-duplicated.

## The lifecycle — three commands

| Command | When | What it writes |
|---|---|---|
| `harness-wf domain-init` | once, at setup/mint | Detects `stack`, scaffolds empty ops slots + `.claude/docs/reference/`. **Never clobbers** an existing manifest. |
| `harness-wf domain-refresh` | when dependencies change | Re-detects and writes **only** `stack`; preserves authored sections + `business`. |
| `harness-wf domain-compile` | when product docs change | Reads `.claude/docs/reference/` → one isolated local-CLI LLM call → writes **only** `business`. No API key. |

`init` creates, `refresh` keeps `stack` current, `compile` keeps `business`
current. The human-authored ops sections you edit by hand. Every command does a
**partial merge** of its own field, so they never stomp each other.

## How it's read at runtime

Two paths, both reading `domain.json` (never `bom.json`):

1. **On-demand pull** — the `domain` MCP exposes `domain_ops(topic)` with
   `topic ∈ stack | environments | test | deploy | infra | references | business |
   all`. Agents call e.g. `domain_ops("deploy")` to get this repo's *real*
   commands instead of guessing. Wired into `CLAUDE.md` as a standing instruction.
2. **Auto-injection** — on planning (**B**) and question (**C**) turns,
   `context_builder` injects the small, capped `business` digest into the system
   prompt, so product judgment-calls stay aligned without the agent asking.

## About `bom.json`

cdxgen's CycloneDX BOM is **scratch output**, not a kept artifact. It's generated
transiently into a temp dir, read once to pull framework names into
`domain.json.stack`, then thrown away. Nothing reads the `bom.json` file — the
useful data lives in `domain.json`. It is gitignored; if a stray cdxgen run drops
one in the tree, it's safe to delete. (If you later add SBOM-consuming tooling —
vuln scanning, license/compliance — that would be the reason to persist it; there
is no such consumer today.)

## One-line mental model

```
domain-init (once) + domain-refresh (stack) + domain-compile (business)
        ↓ all write to
   domain.json   ← the single source of truth
        ↓ read every interaction via
   domain_ops(topic)   (+ business digest auto-injected on B/C turns)
```

Linguist/cdxgen are just *how* `stack` gets filled; the BOM itself is throwaway.
`domain.json` is hand-editable — detection and the LLM only produce a draft.
