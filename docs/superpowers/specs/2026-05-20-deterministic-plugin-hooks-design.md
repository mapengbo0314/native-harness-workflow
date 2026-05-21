# Deterministic Plugin Hooks Design (V4: The Portable Harness)

**Date:** 2026-05-20  
**Status:** Final Approval  
**Scope:** Transforming the auto-generated Claude Code plugin into a self-contained, portable unit that bundles the entire project harness (Agents, Skills, Rules, and Hooks) into a single installable package.

## Problem Statement

The previous design treated the plugin as a "bridge" to live files in the workspace. While this ensured live updates, it failed the "Packaging & Portability" mental model. A true Claude Code plugin should be the **container** for knowledge and logic. 

Furthermore, the initial "Harness Minting" phase (copying boilerplate) and the "Plugin Generation" phase were disconnected, creating a risk where the plugin lacked the full context of the synthesized agents (like the `@domain-sme`).

## Goal

Create a **Zero-Config Portable Harness**. When a user selects "Claude Code" during `harness-wf init`, the system will:
1.  Mint the base harness.
2.  **Migrate** the entire `boilerplate-agent/` and `harness/` logic into a self-contained plugin folder.
3.  Include all 5 Deterministic Hooks to enforce the Hub-and-Spoke model.
4.  Automate CodeGraph onboarding so the plugin is ready for high-performance codebase navigation immediately.

---

## The Self-Contained Architecture

The plugin folder (`.claude/plugin-generated/`) now owns the entire project intelligence.

```text
.claude/plugin-generated/
├── .claude-plugin/
│   ├── plugin.json                # Tools & Hook definitions
│   └── marketplace.json           # Local installation manifest
├── src/
│   ├── hooks/                     # The 5 Deterministic Hooks (Python)
│   ├── tools.py                   # Skill() and Task() handlers
│   └── dispatcher.py              # Orchestrator routing logic
├── agents/                        # Bundled subagent .md files
│   ├── implementer.md
│   ├── planner.md
│   └── domain-sme.md              # Synthesized during init
├── skills/                        # Bundled procedural workflows
│   ├── systematic-debugging/
│   └── test-driven-development/
└── config/                        # Project-specific context
    ├── ddd-context.json           # Live DDD invariants
    └── rules.json                 # Core mandates
```

---

## Architectural Lifecycle Diagram (The Deterministic Loop)

```mermaid
flowchart TD
    User([User Input]) --> UPS{UserPromptSubmit Hook}
    
    %% Input Interception - Matrix Routing
    UPS -- "Detected Stack Trace" --> BranchA[Branch A: Error Router<br/>Compress trace, force debugging] --> LLM
    UPS -- "Build/Create Req" --> BranchB[Branch B: Feature Router<br/>Force Brainstorming + Planner] --> LLM
    UPS -- "How/Where Question" --> BranchC[Branch C: Question Router<br/>Force CodeGraph/Direct Answer] --> LLM
    UPS -- "Clean/Simple Prompt" --> LLM((Claude LLM / Orchestrator))
    
    %% Tool Interception (Pre)
    LLM -- "Call Tool" --> PreHook{PreToolUse Hook}
    
    PreHook -- "Read >100L" --> BlockRead[Block! Enforce CodeGraph Search] --> LLM
    PreHook -- "Edit w/o TDD" --> BlockEdit[Block! Enforce Failing Test] --> LLM
    PreHook -- "Task(Subagent)" --> Lazy[Lazy Load Bundled Persona &<br/>DDD Context from Plugin] --> Exec[Execute Tool]
    PreHook -- "Valid Tool" --> Exec
    
    %% Post Task Phase
    Exec --> PostHook{PostToolUse Hook}
    PostHook -- "Planner Output" --> ArchGuard[Domain Architect Guardrail:<br/>Verify Invariants] --> LLM
    PostHook -- "Other Tools" --> LLM
    
    %% Stop Interception
    LLM -- "Attempt to Finish" --> StopHook{Stop Hook}
    StopHook --> Gate[Run Gatekeeper.py]
    Gate -- "Tests Fail" --> Reject[Block! Force Fixes] --> LLM
    Gate -- "Tests Pass" --> Done([Session Complete])

    classDef hook fill:#f9f,stroke:#333,stroke-width:2px,color:#000;
    classDef block fill:#f99,stroke:#333,stroke-width:2px,color:#000;
    classDef agent fill:#9cf,stroke:#333,stroke-width:2px,color:#000;
    classDef user fill:#ccc,stroke:#333,stroke-width:2px,color:#000;
    
    class UPS,PreHook,PostHook,StopHook hook;
    class BlockRead,BlockEdit,Reject block;
    class LLM agent;
    class User,Done user;
```

---

## Unified Onboarding Flow

1.  **Mint Phase:** `harness-wf init` runs. It creates the project structure, downloads skills, and generates the `@domain-sme`.
2.  **Migration Phase:** `harness/plugin_generator.py` is called. It:
    *   Copies all `.md` files from `.claude/agents/` into the plugin's `agents/`.
    *   Copies all skill folders from `.claude/skills/` into the plugin's `skills/`.
    *   Injects the **Full Matrix Router** into `src/hooks/prompt_interceptor.py`.
3.  **Onboarding Phase:** The user runs `setup_harness.sh`. It:
    *   Builds the CodeGraph index.
    *   Automatically runs `/plugin marketplace add` and `/plugin install`.
    *   **Result:** The user opens Claude Code and the entire harness is "just there," enforcing TDD, protecting tokens, and routing accurately.

---

## Business Value: The Token Efficient Enforcer

*   **Zero-Shot Routing:** By performing heuristic classification in Python (Branch A/B/C/D), we skip the LLM's expensive "thinking" turn entirely.
*   **Trace Compression:** Native Python compression of stack traces reduces input tokens by up to 90% for bug reports.
*   **Portable Knowledge:** The plugin is the "Knowledge Package". It ensures every subagent has immediate access to DDD Context and Invariants without the LLM needing to "find" them.
*   **Engineering Rigor:** Programmatic blocking of non-TDD edits and early success claims ensures high-quality outcomes with less manual oversight.