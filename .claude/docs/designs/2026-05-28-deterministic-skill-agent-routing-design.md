# Deterministic Skill + Agent Routing Design
**Date:** 2026-05-28
**Status:** Proposed

---

## Part 1: Problem Understanding

The harness currently routes user prompts to agents by injecting advisory text into the prompt ("SYSTEM STATE" block). The classification is done by an LLM call, which introduces non-determinism — the same prompt can route differently across runs, and even when the branch is correct, the main Claude agent is only *told* what to do, not *forced* to do it. The goal is to make the routing chain more deterministic and explicit: the right skill gets invoked, the right agent gets dispatched, and the right methodology is followed — with each step being as unambiguous as possible given that we're operating inside Claude Code and Gemini CLI (we cannot mechanically force tool calls, only make them highly directive).

More specifically, the problem has three layers:
1. **Branch → skill routing**: the dispatcher needs a single source-of-truth table that maps each intent branch to both the skill to invoke and the agent expected to execute it.
2. **modifiedPrompt construction**: the hook's output needs to carry both the skill reference AND the expected agent so the orchestrator has two explicit anchors, not one vague suggestion.
3. **Subagent skill access**: the designated agent for a skill (e.g. debugger → `harness-systematic-debugging`) needs to be able to invoke that skill to get its live methodology, while other subagents are still blocked by SUBAGENT-STOP — requiring per-skill agent-aware SUBAGENT-STOP wording.

---

## Part 2: Technical Plan

**1. Unified routing table in the dispatcher (`dispatcher.py`)**
Replace the two separate `BRANCH_SKILLS` and `BRANCH_FALLBACK_AGENTS` dicts with a single `BRANCH_ROUTING` dict. Each entry has three fields: `skill` (the skill to invoke), `agent` (the expected subagent), and `agent_invokes_skill` (whether the designated agent should also invoke the skill itself). The `evaluate_artifacts` method derives `target_skill`, `target_agent`, and `agent_invokes_skill` from this one table.

**2. Adapter: `get_subagent_text_call` gains an optional `skill_name` parameter**
When `agent_invokes_skill` is true, the generated Task call embeds the skill instruction in the description: `Task(subagent_type="debugger", description="Invoke Skill('harness-systematic-debugging') as your first action.")`. When false, it omits it. Gemini equivalent: `@debugger — activate_skill("harness-systematic-debugging") as first action`.

**3. Combined modifiedPrompt in `format_hook_response`**
The directive becomes a two-line chain: `Skill("X") → Task(subagent_type="Y")` for branches with a skill, or just the Task call for branch C. The skill goes first (orchestrator's action), the agent goes second (expected outcome of the skill's Phase 0).

**4. Agent-aware SUBAGENT-STOP in workflow execution skills**
`harness-systematic-debugging` and `harness-test-driven-development` get modified SUBAGENT-STOP blocks that explicitly allow the designated agent (debugger / implementer) through while blocking all other subagents. Meta-routing skills (`harness-brainstorming-plans`, `using-harness-superpowers`, etc.) keep their existing blanket SUBAGENT-STOP unchanged.

**5. Add Phase 0 to `harness-systematic-debugging`**
Currently the only workflow skill missing a Phase 0 dispatch. Needs `Dispatch <!--$ subagent('debugger', 'harness-systematic-debugging') $-->` added, consistent with what was already done for `harness-test-driven-development`.

**6. Sync all generated files**
Three locations per change: boilerplate template, `.claude/plugin-generated/`, `.gemini/`. Dispatcher copies also synced.

---

## Part 3: Alternatives Considered

**Alt A — Remove SUBAGENT-STOP from workflow skills entirely.**
Clean but the user explicitly ruled this out. Blanket removal loses the protection against subagents accidentally re-invoking meta/routing skills in wrong contexts.

**Alt B — Pass skill instructions via Task `prompt` parameter instead of modifying SUBAGENT-STOP.**
The Task call would carry the full skill text inline. Rejected: skill files are long, embedding them in a description string is fragile and defeats the purpose of a live skill system.

**Alt C — Keep modifiedPrompt skill-only (no agent anchor), rely entirely on the skill's Phase 0.**
Simpler, but adds an extra LLM compliance step. The orchestrator must invoke the skill, read Phase 0, then decide to dispatch — three hops instead of two. Rejected in favour of the combined `skill → agent` directive.

**Alt D — Single `BRANCH_ROUTING` table with agent-only routing (no skill), pass skill name in Task description.**
Rejected: loses the orchestrator-level skill invocation. The orchestrator never loads the skill's workflow, so it doesn't understand the context of what it's dispatching.

**Alt E — PreToolUse gatekeeper (enforce at hook level).**
Discussed earlier. Mechanically enforces dispatch but costs tokens on every blocked retry and requires maintaining expected-tool state in `campaign_state.json`. Kept as a backstop option but not the primary mechanism.

---

## Part 4: Detailed Implementation Plan

### `src/harness/runtime/dispatcher.py`
**Rationale:** Replace two separate routing tables with one unified source of truth. Branch D redefined as "any code edit requiring TDD" (was "surgical fast path").
- Task 1: Add `BRANCH_ROUTING` class var replacing `BRANCH_SKILLS` + `BRANCH_FALLBACK_AGENTS`; update Branch D `BRANCHES` description to "Code Edit / TDD Required"
- Task 2: Update `evaluate_artifacts` to derive `target_skill`, `target_agent`, `agent_invokes_skill` from `BRANCH_ROUTING`
- Task 2b: Add guard — if `project_root` absent from context, log warning and return routing with skill=None (no directive emitted)
- Task 3: Remove `BRANCH_SKILLS` and `BRANCH_FALLBACK_AGENTS` class vars

### `src/harness/adapters/base.py`
**Rationale:** Update `get_subagent_text_call` signature to accept optional `skill_name`.
- Task 4: Add `skill_name: Optional[str] = None` parameter to abstract method signature

### `src/harness/adapters/claude.py`
**Rationale:** Implement combined directive format.
- Task 5: Update `get_subagent_text_call(agent_name, skill_name=None)` — when skill_name present: `Task(subagent_type="agent", description="Invoke Skill('skill') as your first action.")`
- Task 6: Update `format_hook_response` — when skill + agent both present: `Skill("X") → Task(subagent_type="Y")` directive; when agent only (C): Task call only; when neither (E): pass-through

### `src/harness/adapters/gemini.py`
**Rationale:** Same as Claude but Gemini syntax.
- Task 7: Update `get_subagent_text_call(agent_name, skill_name=None)` — when skill_name present: `@agent — activate_skill("skill") as first action`
- Task 8: Update `format_hook_response` same logic

### `src/harness/templates/boilerplate/skills/harness-systematic-debugging/SKILL.md`
**Rationale:** Missing Phase 0 dispatch; SUBAGENT-STOP needs to allow debugger through.
- Task 9: Replace blanket SUBAGENT-STOP with agent-aware version (debugger allowed, others blocked)
- Task 10: Add Phase 0 block — `Dispatch <!--$ subagent('debugger', 'harness-systematic-debugging') $-->`

### `src/harness/templates/boilerplate/skills/harness-test-driven-development/SKILL.md`
**Rationale:** SUBAGENT-STOP needs to allow implementer through.
- Task 11: Replace blanket SUBAGENT-STOP with agent-aware version (implementer allowed, others blocked)

### `.claude/plugin-generated/skills/harness-systematic-debugging/SKILL.md`
**Rationale:** Sync generated copy — Claude syntax.
- Task 12: Apply Tasks 9–10 with resolved Claude syntax

### `.claude/plugin-generated/skills/harness-test-driven-development/SKILL.md`
**Rationale:** Sync generated copy.
- Task 13: Apply Task 11

### `.gemini/skills/harness-systematic-debugging/SKILL.md`
**Rationale:** Sync generated copy — Gemini syntax.
- Task 14: Apply Tasks 9–10 with resolved Gemini syntax

### `.gemini/skills/harness-test-driven-development/SKILL.md`
**Rationale:** Sync generated copy.
- Task 15: Apply Task 11

### `.claude/plugin-generated/src/dispatcher.py` + `.gemini/src/dispatcher.py`
**Rationale:** Keep generated runtime copies in sync with source.
- Task 16: Copy `src/harness/runtime/dispatcher.py` to both generated copies

### `src/harness/adapters/codex.py`, `cursor.py`, `generic.py`
**Rationale:** Abstract method signature change must be implemented on all concrete adapters or they break at import time.
- Task 17: Add `get_subagent_text_call(self, agent_name: str, skill_name: str = None) -> str` stub to each — returns `@{agent_name}` as safe default

**Sequencing constraint:** Tasks 4/5/7 (two-arg implementation) MUST complete before Tasks 9/10 (template usage of two-arg form).

---

## Adversary Notes

**Reviewer:** Adversary agent
**Date:** 2026-05-28
**Verdict:** The design has five concrete defects and three structural assumptions that are undocumented. Each item below cites the exact location in the code or the design that triggers it.

---

### Defect 1: Branch D maps `harness-test-driven-development` to surgical edits — this is semantically wrong and internally contradicted

**Evidence (two locations in conflict):**

- `src/harness/runtime/dispatcher.py`, line 99: `"D": "harness-test-driven-development"` — TDD skill is mapped to Branch D.
- `src/harness/runtime/dispatcher.py`, line 91: Branch D is defined as `"Surgical Edit / Fast Path (typo, change color, minor update, fix the, rename)"`.
- `src/harness/runtime/dispatcher.py`, line 256 (`assemble_branch_context`): `"D": "Branch D (Surgical Edit): Bypass heavy planning. Use generalist directly."` — the branch hint for D tells the agent to use the generalist and bypass planning. This contradicts routing it to the `harness-test-driven-development` skill and the `@implementer` agent.

The design in Part 2, Plan item 1 proposes to unify these two dicts into `BRANCH_ROUTING` without acknowledging or resolving this semantic mismatch. If the plan is executed literally, the contradiction is baked into the unified table. No `BRANCH_ROUTING` entry for Branch D can satisfy both "invoke TDD workflow" and "bypass heavy planning; use generalist directly" simultaneously. The design document does not acknowledge this conflict anywhere.

---

### Defect 2: `get_subagent_text_call` is used as a Jinja2 callable during minting — adding `skill_name` breaks its call signature at the template render site

**Evidence:**

- `src/harness/init/minting_engine.py`, line 121: `"subagent": adapter.get_subagent_text_call` — the function is registered as a Jinja2 template callable.
- `src/harness/templates/boilerplate/skills/harness-test-driven-development/SKILL.md`, line 16: `<!--$ subagent('implementer') $-->` — the template calls it with exactly one positional argument.

Part 2, Plan item 2 proposes adding `skill_name: Optional[str] = None` to `get_subagent_text_call`. The abstract method in `base.py` line 75 currently declares `get_subagent_text_call(self, agent_name: str) -> str`. The minting engine passes the function directly as a template callable; the template calls it as `subagent('implementer')`. After the signature change, the function still accepts one positional arg and continues to work correctly in existing templates. However, Tasks 9–10 propose adding `Dispatch <!--$ subagent('debugger', 'harness-systematic-debugging') $-->` to the debugging skill. This two-argument form works only if the template renderer passes both arguments through to the callable. The design does not verify that the Jinja2 rendering context in `minting_engine.py` supports variadic callable invocation from template syntax. If it does not, minting the debugging skill silently produces malformed output or raises a template error.

The design says nothing about testing this rendering path. There is no test task in the implementation plan covering minting the modified debugging skill template.

---

### Defect 3: `codex`, `cursor`, and `generic` adapters are not in scope but implement the same `get_subagent_text_call` and `format_hook_response` signatures that must change

**Evidence:**

- `src/harness/adapters/codex.py`, line 29: `def get_subagent_text_call(self, agent_name: str) -> str`
- `src/harness/adapters/cursor.py`, line 29: `def get_subagent_text_call(self, agent_name: str) -> str`
- `src/harness/adapters/generic.py`, line 29: `def get_subagent_text_call(self, agent_name: str) -> str`

Task 4 modifies the abstract base method in `base.py`. Any concrete subclass that does not override the new signature with the optional `skill_name` parameter will either silently fall back to the base (if one is provided) or raise a `TypeError` at runtime if the caller passes `skill_name` by keyword. The design's task list covers only `claude.py` (Task 5) and `gemini.py` (Task 7). The three other adapters — codex, cursor, generic — are not mentioned. This is an incomplete change to an abstract interface.

---

### Defect 4: The agent-aware SUBAGENT-STOP mechanism is text-based and provides no actual enforcement barrier

**Evidence:**

- Current `harness-systematic-debugging/SKILL.md`, lines 5–7: `<SUBAGENT-STOP> If you were dispatched as a subagent to execute a specific task, skip this skill. </SUBAGENT-STOP>` — this is prose read by the model. It is not a hook, not a guard, not a hard gate.
- Current `harness-test-driven-development/SKILL.md`, lines 6–8: identical blanket stop.

Part 2, Plan item 4 proposes replacing blanket SUBAGENT-STOP with "agent-aware" versions that "explicitly allow the designated agent through while blocking all other subagents." This is still prose. The design does not define what "agent-aware" means mechanically. There is no runtime identity assertion, no token, no state check. The proposal relies entirely on the model reading its own subagent type and self-applying the rule. Any subagent that invokes the skill while ignoring or misreading the modified stop block will proceed unchecked — which is the exact failure mode the stop block was meant to prevent. The design does not acknowledge that the proposed agent-aware stop text offers no stronger enforcement than the blanket stop text it replaces.

---

### Defect 5: `evaluate_artifacts` is the source of `target_skill` but the design conflates it with `classify_intent` as if they are a single step

**Evidence:**

- `src/harness/runtime/dispatcher.py`, lines 325–335: `target_skill = self.BRANCH_SKILLS.get(branch)` is inside `evaluate_artifacts`, which is called only when `"project_root"` is present in context (line 383–386 in `dispatch_agent`).
- `src/harness/templates/boilerplate/hooks/prompt_classifier.py`, line 97: `routing_decision = result.get("routing_decision", {})` — the hook reads `routing_decision` from the dispatch result, which only has `target_skill` if `evaluate_artifacts` was called.

If `project_root` is missing from the hook input (e.g. the hook fires from a context where the agent has not set it, or `resolve_project_root` returns `None` or a fallback), `evaluate_artifacts` is never called, `target_skill` is absent from `routing_decision`, and `format_hook_response` falls through to the `else: modified_prompt = original_prompt` branch — silently producing no directive. The design does not document this failure path, does not add a guard, and does not add any observable signal when this occurs. The unified `BRANCH_ROUTING` table makes the problem harder to notice because the skill assignment is now hidden one level deeper in the table rather than directly visible at the `BRANCH_SKILLS` lookup.

---

### Undocumented Assumption 1: The two-directive prompt format assumes the orchestrator processes them sequentially and does not short-circuit on the first directive

Part 2, Plan item 3 states: `Skill("X") -> Task(subagent_type="Y")`. This assumes the orchestrator will first invoke the skill, read Phase 0, and then dispatch the agent — and that it will not instead treat the Task call as the primary instruction and invoke the agent immediately without running the skill. There is no mechanism in `format_hook_response` (confirmed by reading `claude.py` lines 125–163) that enforces ordering. The current implementation already places the skill directive alone in the prompt (lines 131–138); the proposed change adds the Task call after it. Whether the model obeys the implied sequence is a compliance question, not a structural guarantee. The design classifies this as "two explicit anchors" but both anchors are advisory text.

---

### Undocumented Assumption 2: Phase 0 dispatch syntax `subagent('debugger', 'harness-systematic-debugging')` is an undocumented two-argument extension of the template callable

**Evidence:**

- Existing usage across all skill templates: `<!--$ subagent('implementer') $-->` — one argument only.
- Task 10 proposes: `<!--$ subagent('debugger', 'harness-systematic-debugging') $-->` — two arguments.

The `get_subagent_text_call` signature currently takes only `agent_name`. The design implies that the second argument would instruct the agent to invoke the named skill, but the callable's current implementation (`claude.py` line 122, `gemini.py` line 92) accepts only one argument. This two-argument form does not exist anywhere in the codebase. The design introduces it in Task 10 without defining what the second argument means to the callable, without updating the minting engine's renderer context, and without updating the other two adapters that would need to implement the same behavior. This is an undocumented interface change buried inside a template string.

---

### Undocumented Assumption 3: Task 16 ("copy dispatcher to generated copies") treats generated files as dumb copies, which conflicts with the minting/adapter architecture

**Evidence:**

- `src/harness/adapters/claude.py` `generate_core_infrastructure` method (lines 38–83): generated files undergo path rewriting and platform-variable substitution. They are not verbatim copies.
- `src/harness/init/minting_engine.py`: the minting engine applies tool mappings, Jinja2 template rendering, and placeholder substitution during generation.

Task 16 proposes a raw `cp` of `src/harness/runtime/dispatcher.py` to `.claude/plugin-generated/src/dispatcher.py` and `.gemini/src/dispatcher.py`. The dispatcher does not contain Jinja2 template tokens (confirmed by reading it), so minting is not needed for it specifically. However, the design gives no rationale for why `dispatcher.py` is safe to copy verbatim while skill SKILL.md files require per-platform rendering. If a future change adds platform-conditional logic to the dispatcher, this copy step will silently produce incorrect generated files with no mechanism to detect the divergence. The design should state the invariant being relied on, not just assert the copy step.
