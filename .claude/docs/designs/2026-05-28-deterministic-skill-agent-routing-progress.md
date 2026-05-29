# Progress: Deterministic Skill + Agent Routing
**Design:** `.claude/docs/designs/2026-05-28-deterministic-skill-agent-routing-design.md`
**Started:** 2026-05-28

---

## Tasks

### dispatcher.py
- [x] Task 1: Add `BRANCH_ROUTING` replacing `BRANCH_SKILLS` + `BRANCH_FALLBACK_AGENTS`; update Branch D description
- [x] Task 2: Update `evaluate_artifacts` to derive from `BRANCH_ROUTING`
- [x] Task 2b: Add project_root guard (log warning, fallback to ".")
- [x] Task 3: Remove `BRANCH_SKILLS` and `BRANCH_FALLBACK_AGENTS` class vars

### base.py
- [x] Task 4: Add `skill_name: str = None` to `get_subagent_text_call` abstract method

### claude.py
- [x] Task 5: Update `get_subagent_text_call(agent_name, skill_name=None)`
- [x] Task 6: Update `format_hook_response` — combined `Skill("X") → Task(...)` directive

### gemini.py
- [x] Task 7: Update `get_subagent_text_call(agent_name, skill_name=None)`
- [x] Task 8: Update `format_hook_response` same logic

### boilerplate skill files
- [x] Task 9: `harness-systematic-debugging/SKILL.md` — agent-aware SUBAGENT-STOP (debugger allowed)
- [x] Task 10: `harness-systematic-debugging/SKILL.md` — add Phase 0 dispatch block
- [x] Task 11: `harness-test-driven-development/SKILL.md` — agent-aware SUBAGENT-STOP (implementer allowed)

### generated .claude skill files
- [x] Task 12: `.claude/plugin-generated/skills/harness-systematic-debugging/SKILL.md` — resolved Claude syntax
- [x] Task 13: `.claude/plugin-generated/skills/harness-test-driven-development/SKILL.md` — resolved Claude syntax

### generated .gemini skill files
- [x] Task 14: `.gemini/skills/harness-systematic-debugging/SKILL.md` — resolved Gemini syntax
- [x] Task 15: `.gemini/skills/harness-test-driven-development/SKILL.md` — resolved Gemini syntax

### dispatcher sync + remaining adapters
- [x] Task 16: Copy `src/harness/runtime/dispatcher.py` to both generated plugin copies
- [x] Task 17a: `codex.py` stub — `get_subagent_text_call(agent_name, skill_name=None)`
- [x] Task 17b: `cursor.py` stub — `get_subagent_text_call(agent_name, skill_name=None)`
- [x] Task 17c: `generic.py` stub — `get_subagent_text_call(agent_name, skill_name=None)`
