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

| Capability | Claude | Gemini | Codex | Cursor |
|---|:--:|:--:|:--:|:--:|
| MCP (`domain_ops`, codegraph) | ✅ | ✅ | ✅ | ✅ |
| Per-turn context injection | ✅ | ✅ | ⚠️ append-only | ❌ none |
| Per-turn prompt rewrite (routing) | ✅ | ✅ | ❌ | ❌ |
| Tool-use gating / enforcement hooks | ✅ | ✅ | ✅ | ✅ (`permission`) |
| Native subagents | ✅ | n/a | ✅ `.codex/agents/*.toml` | ✅ `.cursor/agents/*.md` |
| Native skills | ✅ | ✅ | ✅ `$skill` | ✅ `/skill` |

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
- ⏳ **Deferred** (this document is the spec): the mapping corrections above, the
  Codex `format_hook_response` rewrite to `additionalContext`, and the
  Cursor-native rules-file + subagent generation. These change minting output and
  snapshots and should be done as a dedicated pass.

## Caveats

Cursor and Codex iterate quickly (Cursor hooks/subagents/skills landed in 1.7–2.4;
Codex hooks are behind a `features.lifecycle.hooks` flag). Re-verify the schemas
above before the implementation pass. In particular, Cursor's "no prompt
injection" limitation is the subject of open feature requests and may relax.
