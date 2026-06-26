# Harness Master Configuration Tree

This document outlines the complete architectural feature set of the Agentic Harness, formatted as a nested configuration tree. This structure demonstrates how linear pipelines, cross-cutting wrappers, standalone services, and modular components (agents/skills) can be represented and toggled.

```yaml
features:
  # ---------------------------------------------------------
  # 1. The Core Execution Pipeline (Linear Dependencies)
  #    These depend on each other sequentially.
  # ---------------------------------------------------------
  pipeline:
    hooks_engine:
      enabled: true
      dispatcher:
        enabled: true
        context_injection:
          enabled: true
          # Micro-toggles for specific context injections
          inject_business_rules: true # Reads business section of domain.json
          inject_missing_artifacts: true # Appends missing docs to SYSTEM STATE

  # ---------------------------------------------------------
  # 2. Cross-Cutting Wrappers (Independent)
  #    These wrap the execution but don't break the pipeline if disabled.
  # ---------------------------------------------------------
  wrappers:
    telemetry:
      enabled: true # Toggles the @observe wrapper (LANGFUSE_ENABLED)
      provider: "langfuse"
    security_guardrails:
      enabled: true # Enforced inside pre_tool_use
      block_dangerous_rm: true # Prevents rm -rf / commands
      block_env_access: true # Prevents reading sensitive .env files
    methodology_enforcement:
      enabled: true # Enforced inside pre_tool_use
      require_tdd: true # Blocks editing source code if a test hasn't been written

  # ---------------------------------------------------------
  # 3. Standalone Services (Background Processes)
  # ---------------------------------------------------------
  services:
    mcp_domain_server:
      enabled: true # The `domain_ops` local server

  # ---------------------------------------------------------
  # 4. Agent Personas (Modular Sub-Agents)
  #    Disabling one forces the dispatcher to use the fallback (@generalist).
  # ---------------------------------------------------------
  agents:
    generalist:
      enabled: true # The default fallback
    debugger:
      enabled: true # Triggered by Branch A (Bugs)
    planner:
      enabled: true # Triggered by Branch B (Discovery Phase)
    implementer:
      enabled: true # Triggered by Branch B (Execution Phase)
    verifier:
      enabled: true
    reviewer:
      enabled: true
    adversary:
      enabled: true

  # ---------------------------------------------------------
  # 5. Specialized Skills (Modular Workflows)
  #    Disabling these removes them from the agent's available tools.
  # ---------------------------------------------------------
  skills:
    using-harness-superpowers:
      enabled: true # The master skill loader
    harness-brainstorming-plans:
      enabled: true
    harness-test-driven-development:
      enabled: true
    harness-systematic-debugging:
      enabled: true
    harness-subagent-driven-development:
      enabled: true
    harness-executing-plans:
      enabled: true
    harness-dispatching-parallel-agents:
      enabled: true
    harness-requesting-code-review:
      enabled: true
    harness-finishing-a-development-branch:
      enabled: true
    diagnose:
      enabled: true
    improve-codebase-architecture:
      enabled: true
    ddd-alignment:
      enabled: true
    grill-me:
      enabled: true
    grill-with-docs:
      enabled: true
    meta-learning:
      enabled: true
    # ECC-ported skill toggles (Phase 0 feature-toggle surface)
    continuous-learning: true  # Persist learnings across sessions
    search-first: true         # Enforce search gate before implementation
    adversary-pipeline: true   # Enable adversary review pass in pipeline

  # ---------------------------------------------------------
  # 5b. ECC-Ported Feature Toggles (Phase 0 — operator YAML surface)
  #     Operators edit features.yaml then run `harness-wf features sync`.
  #     The compiled features.json is machine-read; never hand-edit it.
  # ---------------------------------------------------------
  rules_packs:
    enabled: true          # Enable language-specific rule packs
    languages:             # Per-language bool leaves freely allowed here
      # python: true
      # typescript: true

  services:
    session_memory:
      enabled: true        # Persist session context across prompts

  hooks:
    session_end:
      learning_extraction: true  # Extract + store learnings at session end

  pipeline:
    dispatcher:
      gates:
        search_first: true    # Require search step before implementation dispatch
        adversary_exit: true  # Enable adversary exit gate in pipeline

  # Plan A–E dispatch branches (implemented: hook_common.effective_branch).
  # Disabling a branch degrades that intent to plan_e (answer-only).
  # plan_e is the always-on terminal fallback and is never degraded.
  branches:
    plan_a_bugs: true        # Bug / error / stack-trace intents
    plan_b_discovery: true   # Design / planning / brainstorming intents
    plan_c_readonly: true    # Explain / where / which-file questions
    plan_d_execution: true   # Implement / create / refactor intents
    plan_e_answer: true      # Answer-only fallback (always on)

  # ---------------------------------------------------------
  # 6. Specific Hook Listeners (The physical triggers)
  #    Disabling these stops listening to specific platform events.
  # ---------------------------------------------------------
  hooks:
    prompt_classifier:
      enabled: true # Listens to user inputs. Disabling this kills the pipeline.
    pre_tool_use:
      enabled: true # Listens before tools fire. Disabling this kills security/TDD wrappers.
    post_tool_use:
      enabled: true # Listens after tools fire.
    notify_compression:
      enabled: true # Listens when context window is full.
```
