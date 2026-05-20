# Orchestrator Plugin System Design

**Date:** 2026-05-20  
**Status:** Design Review  
**Scope:** Auto-generated Claude Code plugin system for any project using the harness setup

## Problem Statement

Any project that uses the harness setup system (e-2-g, future projects, etc.) has:
- Custom orchestrator for agent routing
- Specialized agents (planner, implementer, reviewer, etc.)
- Project-specific rules and mandates
- DDD context and ubiquitous language definitions

**Current Gap:** When Claude Code runs in a project, there's no guarantee that the orchestrator is invoked for agent dispatching. This breaks consistency and determinism—the orchestrator's routing logic, guardrails, and mandates may be bypassed.

**Goal:** Create a generic Claude Code plugin generation system that any harness-setup project can use. Each project gets its own plugin that transparently enforces orchestrator dispatch, ensuring all agent invocations go through the orchestrator's routing and validation layer.

## Solution Overview

### Architecture

The plugin is **auto-generated** by the harness setup system. When a user completes harness configuration and selects Claude Code as a target platform, the harness automatically generates a Claude Code plugin tailored to the project.

**Plugin responsibilities:**
1. Register with Claude Code on startup (only in e-2-g repo)
2. Intercept all agent invocations
3. Validate against project rules/mandates
4. Route through the orchestrator
5. Return dispatched results transparently

### Generated Plugin Structure

```
.claude/plugin-generated/
├── plugin.json                    # Claude Code plugin manifest
├── src/
│   ├── orchestrator_plugin.py     # Plugin entry point
│   ├── dispatcher.py              # Orchestrator dispatch logic
│   └── interceptor.py             # Hook/interception handler
├── config/
│   ├── agents.json                # Agent definitions (copied from harness)
│   ├── orchestrator.json          # Orchestrator routing (copied from harness)
│   ├── ddd-context.json           # DDD context (from harness setup)
│   └── rules.json                 # Project mandates/rules (from harness rules/)
└── pyproject.toml                 # Dependencies (minimal)
```

### Generation Flow

**User Experience:**
```
1. User runs: harness setup
2. System: Guides through agent minting, DDD context, rules, orchestrator config
3. User: Selects "Claude Code" from platform menu
4. User: Selects "orchestrator-plugin" as an extension in ONBOARDING_DOMAIN.md
5. System: Auto-generates plugin in .claude/plugin-generated/
6. User: Runs setup_harness.sh script
7. Script: Installs plugin via `/plugin install orchestrator-plugin@<path> --project`
8. Plugin: Runs in background, enforces orchestrator dispatch
```

**Implementation:**
The minting engine (`harness/minting_engine.py`) integrates plugin generation:
- When Claude Code is selected as platform and orchestrator-plugin is in ONBOARDING_DOMAIN.md
- Minting engine generates plugin in `.claude/plugin-generated/`
- Reads harness configuration (agents, orchestrator, rules, DDD context)
- Generates `plugin.json` manifest
- Generates `src/orchestrator_plugin.py` with project-specific routing
- Copies/exports agents, rules, and DDD context
- Generates `pyproject.toml` with minimal dependencies
- Adds installation command to `setup_harness.sh` script (via `/plugin install` mechanism)

### Runtime Behavior

**Activation:**
- Plugin activates when Claude Code is running in a project that has been set up with the harness (detected via `.claude/orchestrator.md` or config marker)
- Each project's plugin only activates in that specific project
- Does not activate in repositories without harness setup

**Dispatch Interception:**
- Plugin hooks Claude Code's agent dispatching mechanism (similar to claude-code-harness)
- When an agent is requested, the plugin:
  1. Validates the request against project rules
  2. Routes through the orchestrator (applies routing logic)
  3. Dispatches the resolved agent
  4. Returns result transparently to Claude Code

**Transparency:**
- User experience is unchanged—agents work as normal
- Orchestrator enforcement happens silently in the background
- No user-facing commands required

### Key Design Decisions

**Why Auto-Generated?**
- Ensures plugin always reflects current harness configuration
- Eliminates manual sync burden
- Plugin is tailored to the specific project setup

**Why Packaged Inside Plugin?**
- Self-contained deployment (no external harness dependency at runtime)
- Guaranteed consistency—plugin has the exact config it was generated from
- Easier to update (regenerate when harness changes)

**Why .claude/plugin-generated/?**
- Clearly marks it as generated (not hand-edited)
- Kept separate from source code
- Can be .gitignored if desired, or committed for reproducibility

## Implementation Phases

### Phase 1: Minting Engine Integration
Extend `harness/minting_engine.py`:
- Detect when Claude Code platform is selected + orchestrator-plugin is in ONBOARDING_DOMAIN.md
- Add `generate_orchestrator_plugin()` function that:
  - Creates `.claude/plugin-generated/` directory structure
  - Generates `plugin.json` manifest (with plugin metadata)
  - Generates `src/orchestrator_plugin.py` entry point
  - Copies agents, orchestrator config, rules, DDD context
  - Generates `pyproject.toml` with dependencies
- Integrate plugin installation into `setup_harness.sh` script generation (via `/plugin install` command)

### Phase 2: Plugin Dispatcher Logic
Implement `src/orchestrator_plugin.py`:
- Claude Code plugin entry point
- Hook registration for agent dispatch interception
- Orchestrator dispatch wrapper
- Rule validation against project mandates
- Agent routing through orchestrator
- Result passthrough to Claude Code

### Phase 3: Testing & Integration
- Test plugin generation via minting engine
- Verify plugin activation/deactivation in different projects
- Verify orchestrator dispatch is always invoked
- Integration test with Claude Code plugin system and harness hooks

## Success Criteria

1. **Consistency:** Every agent invocation in e-2-g repo routes through orchestrator (100% coverage)
2. **Transparency:** Users don't see any difference in Claude Code behavior
3. **Determinism:** Same project setup always produces the same plugin
4. **Maintainability:** Plugin can be regenerated by re-running harness setup

## Dependencies & Constraints

**Dependencies:**
- Python harness modules (orchestrator, agents, rules)
- Claude Code plugin system (hook mechanism, registration)
- Minimal external Python packages (to be determined during implementation)

**Constraints:**
- Plugin only activates in the project it was generated for (scoped deployment)
- Auto-generation must happen after harness setup completes
- Plugin must be transparent (no new CLI commands required)
- Compatible with harness agents and orchestrator from any project
- Must work for current and future harness-setup projects

## Alternatives Considered

1. **Manual Plugin (Not Chosen):** Users manually create plugin after setup
   - Risk: Setup/plugin get out of sync
   - More effort for users
   - Chosen: Auto-generation instead

2. **Plugin as Harness Dependency (Not Chosen):** Plugin calls harness as external service
   - Adds complexity (IPC/RPC)
   - Slower dispatch
   - Chosen: Self-contained plugin instead

3. **Explicit Skill Wrapper (Not Chosen):** Users invoke `/orchestrate` commands
   - Not transparent, requires user action
   - Chosen: Hook-based interception instead

## Open Questions / Next Steps

1. **Distribution:** Should generated plugin be committed to .git or generated on-demand?
2. **Regeneration:** Should harness provide a command to regenerate plugin if setup changes?
3. **Versioning:** How to version the plugin (manual or auto-derived from harness)?
4. **Testing:** What's the test strategy for hook-based interception?

---

**Next Phase:** Implementation planning via writing-plans skill
