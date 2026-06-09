# Platform support — capabilities, limitations & correct mappings

The harness was designed for **Claude Code**. Other platforms (gemini, codex,
cursor) are supported through `src/harness/adapters/` + `platform_profiles.json`,
but they do **not** all support the harness's core mechanism equally. This page
documents what works, what doesn't, and the verified-correct per-platform
conventions (researched against each vendor's official docs, June 2026).

## The core mechanism (and why it doesn't fully port)

On Claude, a `UserPromptSubmit` hook fires before the model reads each prompt and:
1. **classifies** the prompt (branch A–E),
2. **routes** it to a target agent (`@planner`/`@implementer`/…),
3. **injects** the `=== SYSTEM STATE ===` block, JIT rules, and the `business`
   digest — by **rewriting the prompt** (prepend routing + append context).

This depends on two hook abilities: **inject context per turn** and **rewrite
the prompt**. Not every platform's hooks can do both.

## Support matrix

| Capability | Claude | Gemini | Codex | Cursor | Generic |
|---|:--:|:--:|:--:|:--:|:--:|
| MCP (`domain_ops`, codegraph) | ✅ | ✅ | ✅ | ✅ | ❌ N/A (no convention) |
| Per-turn context injection | ✅ | ⚠️ append-only | ⚠️ append-only | ❌ none | ❌ |
| Per-turn prompt rewrite (routing) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Tool-use gating / enforcement hooks | ✅ | ✅ `BeforeTool` | ✅ | ✅ (`permission`) | ❌ |
| Native subagents | ✅ | ✅ `.gemini/agents/*.md` (`@agent`) | ✅ `.codex/agents/*.toml` | ✅ `.cursor/agents/*.md` | n/a |
| Native skills | ✅ | ✅ `activate_skill` (agent-only) | ✅ `$skill` | ✅ `/skill` | n/a |

> **Correction (Gemini deep-research pass, June 2026).** The earlier matrix
> claimed Gemini supported per-turn prompt rewrite + context injection. That is
> wrong: Gemini's prompt-submit hook is **`BeforeAgent`** (there is **no**
> `UserPromptSubmit` event), and `BeforeAgent` is **append-only** — its
> `hookSpecificOutput.additionalContext` is "text appended to the prompt for this
> turn"; it **cannot rewrite the prompt**. So Gemini behaves like Codex, not like
> Claude. See "Gemini" below.

## Codex — works, with a hook-output rework

Codex's hook system mirrors Claude's **event names verbatim** (`UserPromptSubmit`,
`PreToolUse`, `PostToolUse`, `PreCompact`, `Stop` …), so `event_mappings = {}` is
fine. But two things differ:

- **Append-only context, no prompt rewrite.** `UserPromptSubmit` can inject
  context via `hookSpecificOutput.additionalContext` (or stdout), and can block
  (`decision: "block"` / exit 2) — but it **cannot rewrite the prompt**. So
  routing must become *injected instruction* ("act as @planner; SYSTEM STATE:
  …") rather than a prepended/rewritten prompt. Functionally equivalent.
- **`deny_unknown_fields`.** Codex rejects unknown hook-output fields. The
  harness's current `format_hook_response` emits invented fields
  (`classification`, `modifiedPrompt`, `system_prompt_extension`, `target_agent`,
  `hookSpecificOutput.modifiedPrompt`/`.target_agent`) that Codex will reject or
  ignore. Correct output: `continue`, `systemMessage`, `decision`/`reason`, and
  `hookSpecificOutput { hookEventName, additionalContext }`.

**Verdict:** Codex can run the full harness router, re-expressed as
context-injection. It needs a `format_hook_response` rewrite + the mapping fixes
below.

## Cursor — per-turn routing is not possible; use the Cursor-native model

Cursor has hooks (since 1.7), but `beforeSubmitPrompt` can only return
`{continue, user_message}` — it **cannot inject context or rewrite the prompt**
(an open Cursor feature request). There is no per-turn channel for the SYSTEM
STATE block or forced routing. The harness's `format_hook_response` schema is
fields Cursor ignores entirely.

**Decision (accepted): per-turn routing is OFF for Cursor.** Instead, deliver the
harness's value through Cursor-native mechanisms — a decomposition of the router:

| Router function | Cursor-native replacement |
|---|---|
| Always-on rules (graph-first, TDD, "use `domain_ops`", agent mandates) | **Rules files** `.cursor/rules/*.mdc` (`alwaysApply: true`) or `AGENTS.md` — auto-injected every conversation |
| Specialized agents (`@planner`, …) | **Native subagents** `.cursor/agents/<name>.md`, invoked `/planner` or auto-selected |
| On-demand project ops/business | **MCP `domain_ops`** (already wired in `.cursor/mcp.json`) |
| One-time session preamble | **`sessionStart` hook** → `additional_context` (once/session) |
| Tool gating / enforcement | **`preToolUse` / `beforeShellExecution`** hooks with `permission: allow/deny/ask` |
| Dynamic per-turn classify + force-route | ❌ **No equivalent** — the model self-directs via the above |

**Verdict:** Cursor keeps the *content* of the harness (rules + specialists +
project ops) but loses the *automatic per-turn routing determinism*. This is how
Cursor is designed to work; it's a deliberate reduction, not a bug.

## Gemini — append-only hook (like Codex), validated June 2026

Gemini CLI was the one platform never deep-researched. Validation against the
official docs (geminicli.com) and `google-gemini/gemini-cli`:

- **Hook events are a different taxonomy, not Claude's.** Gemini's events are
  `SessionStart`, `SessionEnd`, **`BeforeAgent`** (fires "after user submits
  prompt, before planning"), `AfterAgent`, `BeforeModel`, `AfterModel`,
  `BeforeToolSelection`, **`BeforeTool`**, **`AfterTool`**, **`PreCompress`**,
  `Notification`. There is **no** `UserPromptSubmit` / `PreToolUse` /
  `PostToolUse` / `PreCompact`. The minted `hooks.json` ships Claude's event-name
  keys, so `install_hooks` MUST remap **all four**:
  `UserPromptSubmit→BeforeAgent`, `PreToolUse→BeforeTool`,
  `PostToolUse→AfterTool`, `PreCompact→PreCompress`. (Previously only the last
  two were remapped — the classifier + security hooks were bound to non-existent
  events and never fired. **Fixed.**)
  Refs: <https://geminicli.com/docs/hooks/reference/>, <https://geminicli.com/docs/hooks/>.
- **`BeforeAgent` is append-only — no prompt rewrite.** Its
  `hookSpecificOutput.additionalContext` is "text appended to the prompt for
  this turn"; valid output fields are `continue`, `decision`, `reason`,
  `systemMessage`, and `hookSpecificOutput { hookEventName, additionalContext }`.
  So Gemini gets the **same honest treatment as Codex**: `format_hook_response`
  folds the routing decision + SYSTEM STATE into `additionalContext` and emits
  only valid fields (no invented `modifiedPrompt` / `systemPromptExtension` /
  `target_agent`). **Fixed** (shared `_format_append_only_hook_response`).
- **`@{agent}` subagent syntax is real.** `@codebase_investigator <task>` forces
  a specific subagent; the CLI injects a system note nudging that subagent tool.
  Subagents are `.gemini/agents/*.md` (markdown + YAML frontmatter). **Confirmed
  correct.** Ref: <https://github.com/google-gemini/gemini-cli/blob/main/docs/core/subagents.md>.
- **`GEMINI.md` is the right rules file** (or `AGENT.md`). **Confirmed correct.**
- **`manifest_format = "markdown"`** for agents. **Confirmed correct.**
- **`activate_skill("{skill}")` — kept, with a caveat.** `activate_skill` is a
  real Gemini tool, but the docs say it is **"used exclusively by the Gemini
  agent; you cannot invoke this tool manually."** It is emitted inside the
  injected dispatch directive as a natural-language nudge to the model (which
  *can* call it), which is defensible. There is no documented user/hook syntax to
  force a skill (users reference `@skills/<name>/SKILL.md`). Changing the
  skill-trigger convention is a semantic decision deferred to a dedicated pass.
  Ref: <https://geminicli.com/docs/tools/activate-skill/>.

**Verdict:** Gemini runs the harness router re-expressed as context-injection
(identical mechanism to Codex), now with correct hook-event names. `gemini.py` is
profile-driven and byte-identical to the runtime adapter (drift test covers
gemini).

## Generic — domain MCP is N/A (no registration convention)

`generic` (`.agents/`) is a catch-all for "no specific CLI". Each real platform
registers the `domain` MCP through its own mechanism — Codex `.codex/config.toml`,
Cursor `.cursor/mcp.json`, Gemini the `gemini mcp add` CLI — but there is **no
universal `.agents/mcp.json` standard** to target. Fabricating one would be
dishonest, so **domain MCP registration is N/A for generic**: `configure_cli`
is a deliberate no-op and the mint writes nothing claiming `domain_ops` for the
generic platform. (Pinned by `test_generic_configure_cli_is_noop_no_domain_mcp`.)
If a `.agents/mcp.json` convention emerges, wire it then.

## Verified-correct mappings (current → correct)

Researched against official docs. These are **not yet applied** — they require a
minting-output rework (and snapshot updates) and are tracked here for the
implementation pass.

### Cursor
| Field | Current (wrong) | Correct |
|---|---|---|
| `subagent_invocation` | `@{agent} …` | `/{agent} …` ( `@` = file/context mentions, **not** agents) |
| `skill_invocation` | `Use {skill}` | `/{skill}` (or auto by description) |
| `rules_pointer_files` | `.cursorrules`, `.github/copilot-instructions.md` | `.cursor/rules/*.mdc` and/or `AGENTS.md` (`.cursorrules` deprecated; copilot file is foreign) |
| hook config | scanned `.cursor/hooks` dir | single `.cursor/hooks.json` manifest |
| `tool_mappings` | `{}` | `replace`→`edit_file`, `write_file`→`edit_file`, `run_shell_command`→`run_terminal_cmd`, `grep_search`→`grep`/`codebase_search` |
| `format_hook_response` | invented routing schema | N/A — Cursor can't route via hook (see above) |

### Codex
| Field | Current (wrong) | Correct |
|---|---|---|
| `subagent_invocation` | `Hand off to {agent}: …` | `.codex/agents/*.toml` + explicit spawn (no "Hand off" convention) |
| `skill_invocation` | `Activate skill {skill}` | `$skill-name` (or `/skills`) |
| `rules_pointer_files` | `CODEX.md` (fictional) | `AGENTS.md` (global `~/.codex/AGENTS.md` + project `AGENTS.md`) |
| `manifest_format` | `yaml` | **TOML** for agents (skills use `SKILL.md` + YAML frontmatter) |
| `event_mappings` | `{}` | ✅ correct (Codex uses Claude's event names) |
| `tool_mappings` | `{}` | Claude `Bash`→`shell`, `Edit`/`Write`→`apply_patch`, etc. |
| `format_hook_response` | invented fields (rejected by `deny_unknown_fields`) | `hookSpecificOutput.additionalContext` + `continue`/`systemMessage`/`decision` |

## Implementation status

- ✅ **Done** (PR #36): domain MCP registration (gemini/cursor/codex), platform-aware
  manifest paths, the `${HARNESS_PLUGIN_ROOT}` hook-placeholder fix, and
  `resolve_plugin_root` env vars. cursor/codex hooks now *launch*.
- ✅ **Done** (Codex pass): the Codex mapping corrections, the Codex
  `format_hook_response` rewrite to `additionalContext`, and `AGENTS.md`
  generation.
- ✅ **Done** (Cursor pass): the Cursor mapping corrections
  (`rules_pointer_files`→`AGENTS.md`, `/agent` & `/skill` invocation,
  `tool_mappings`→`edit_file`/`run_terminal_cmd`/`grep`/`read_file`); the honest
  `format_hook_response` (Cursor's `beforeSubmitPrompt` can only return
  `{continue, user_message}`, so the hook emits `{"continue": true}` and per-turn
  routing is OFF); `AGENTS.md` rules-pointer generation; and native subagents
  emitted under `.cursor/agents/*.md` with Cursor-mapped tool names. `cursor.py`
  is now profile-driven and byte-identical to the runtime adapter (drift test
  extended to cursor).
- ✅ **Done** (Gemini deep-research pass): validated the whole Gemini profile +
  adapter against official docs. Fixed `event_mappings` (added
  `UserPromptSubmit→BeforeAgent`, `PreToolUse→BeforeTool`) and the `gemini.py`
  `install_hooks` rewrite to remap **all four** Claude event names — minted
  `hooks.json` now binds to Gemini's real events (was silently dropping the
  classifier + security hooks). Rewrote `format_hook_response` to the honest
  append-only shape (shared `_format_append_only_hook_response` with Codex):
  routing + SYSTEM STATE fold into `additionalContext`, no invented fields;
  `gemini.py` now delegates to the runtime adapter (drift-pinned). Removed an
  unused `import shlex`. Confirmed `@{agent}`, `GEMINI.md`, `manifest_format`
  correct; kept `activate_skill(...)` with a documented caveat (agent-only tool).
- ✅ **Done** (nits): `cli.py --platform` now has
  `choices=[claude,gemini,codex,cursor,generic]` (invalid values fail with exit
  2). The project-ops rules pointer wording "the plugin's `domain/domain.json`"
  is now platform-neutral ("the deployed `domain/domain.json`") so it no longer
  claims a plugin on non-plugin platforms (GEMINI/AGENTS); all four minted-rules
  snapshots regenerated.
- ✅ **Done** (Generic): documented domain MCP as **N/A** for generic (no
  registration convention); `configure_cli` stays a no-op and nothing claims
  `domain_ops` for generic.
- ⏳ **Deferred** (Gemini): the user/hook-facing **skill-trigger convention**
  (`activate_skill` is agent-only; users reference `@skills/<name>/SKILL.md`).
  Re-expressing the dispatch directive's skill reference is a semantic change to
  the routing language across platforms — deferred to a dedicated pass.
- ⏳ **Deferred** (Cursor): the `.cursor/agents/*.md` frontmatter still uses the
  shared boilerplate shape (`name`, `description`, `tools` — with a duplicated
  `edit_file` where `replace`+`write_file` collapse). Cursor's native subagent
  frontmatter wants `name`, `description`, `model`. Emitting a Cursor-specific
  frontmatter (add `model`, dedup `tools`) is a shared-boilerplate generator
  rework (it affects every platform's agent emission), so it is deferred to a
  dedicated agent-frontmatter pass rather than half-migrated here.

## Caveats

Cursor and Codex iterate quickly (Cursor hooks/subagents/skills landed in 1.7–2.4;
Codex hooks are behind a `features.lifecycle.hooks` flag). Re-verify the schemas
above before the implementation pass. In particular, Cursor's "no prompt
injection" limitation is the subject of open feature requests and may relax.
