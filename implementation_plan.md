# Harness Generator Overhaul: Implementation Plan

> **Goal**: Upgrade the `src/harness` Python framework to be a world-class Minting Engine that generates Level 4+ Agentic Harnesses.
> **Audit Reference**: `harness_audit.md` — 20 gaps identified.

> [!IMPORTANT]
> **Architecture Strategy**: The `src/harness` CLI is purely a **Minting Engine**. We are redesigning it to mint structural safety (hooks, databases, state scripts) rather than just copying markdown prose. This aligns strictly with `hjasanchez/agentic-engineering` (shifting from probabilistic LLM behavior to hard-coded state machines).

---

## Phase 0: Triage — Stop the Template Bleeding
**Timeline**: Day 1
**Focus**: Fixing structural rot in `src/harness/templates/boilerplate/`.

### Task 0.1: Clean up Agent Templates
- Remove phantom references to `@architect`, `pocock-tdd`, and `@../rules/indexer_mandate.md`.
- Ensure `orchestrator.md` only references existing agents.
- **Note**: Preserving 10+ agent specialization per user request.

### Task 0.2: Clean up Skill Templates
- Remove orphaned or domain-specific skills (`fastapi`, `nextjs`, `agentic-eval`, `prompt-engineer`) to keep the boilerplate lean.

---

## Phase 1: Re-Architecture of the Minting Engine
**Timeline**: Week 1

### Task 1.1: Platform-Targeted Generation & Selective Skill Minting
Update `minting_engine.py` to recognize the target platform and domain:
- **Platform-Targeted**: 
  - If target is Gemini: Mint `.gemini/` containing the markdown rules and scripts.
  - If target is Claude Code: Mint `.claude/` containing the markdown rules, AND the execution hooks.
- **Selective Skill Minting**: 
  - Generate a lightweight `skills_index.json` during minting.
  - Only package `SKILL.md` files relevant to the detected stack/domain.
  - Create `bin/activate_skill.py` (a script/tool) into the target workspace to allow lazy-loading of full skill content.

### Task 1.2: Native Initialization & Unified State
- Integrate boilerplate generation into `python -m harness --init`.
- **Unified State**: Generate a single **`campaign_state.json`** tracker into the target workspace's explicit harness directory (e.g., `.claude/campaign_state.json` or `.gemini/campaign_state.json`, consolidating tasks, handoffs, and general state). Every script/hook MUST use a single, unified path resolver.
- **Mandate**: All state writes MUST use atomic "write-to-tmp-then-replace" logic to prevent corruption during forced exits or cutoffs.

---

## Phase 2: Hardening the V4 Hook Design (Claude Code Only)
**Timeline**: Week 2
**Focus**: Solving Cutoff, Handoff, and Hook Insufficiency via Native Scripts.

### Task 2.1: Deterministic Matrix Routing & Prompt Assembly
- **Hook 1**: `intent_classifier.py` (`UserPromptSubmit`)
  - **Action**: Classifies the user prompt into Branch A/B/C/D and writes the classification to `campaign_state.json`.
  - **Token Optimization**: Remove "Chain of Thought" from the LLM classifier prompt.
- **Dispatcher Logic**: Modify `src/harness/dispatcher.py` to assemble branch-specific minimal prompts.
  - **Branch-Locked Context**: Physically assemble the prompt by excluding irrelevant rules/skills based on the active task in `campaign_state.json`.
- **Shared Mandate Resolver**: Modify `minting_engine.py` to use Context Pointers instead of recursive prompt expansion to deduplicate shared rules.

### Task 2.2: JSON-First Parsing & Branch D Firewall
- **Hook**: `pre-write-guard.py` (`PreToolUse`)
  - **Action**: The hook MUST parse stdin as strict JSON to extract tool arguments.
  - **Branch D Enforcement**: If `campaign_state.json` indicates Branch D (Fast Path), it strictly intercepts and blocks any attempt to use the `Task("@planner")` or `Task("@verifier")` tools, returning **`exit 2`**.
  - **Anti-Sabotage**: Strictly block ANY `replace_file_content` targeting `campaign_state.json`, `.claude/settings.json`, or `.env`. Return **`exit 2`**.
  - **Shell Proxy Firewall**: Intercept `Bash` tool calls. If it detects modifications to harness internals (e.g., `echo "{}" > .claude/settings.json`), return **`exit 2`** instantly.

### Task 2.3: Deterministic Handoff & Cutoff Management
- **Hook**: `context_monitor.py` (`PreToolUse`)
- **Action**: Monitor `remainingTokens`. When tokens hit 85% capacity:
  1.  **Serialize State**: Write an atomic update to `campaign_state.json` containing `last_branch`, `current_task`, and `completed_steps`.
  2.  **Generate Artifact (ykdojo style)**: Generate `HANDOFF.md` with strict sections: `Goal`, `Current Progress`, `What Worked`, `What Didn't Work` (Failed attempts), and `Next Steps`.
  3.  **Hard Block**: Return **`exit 2`** with a feedback message: `CONTEXT LIMIT REACHED. Run /clear then 'python3 harness_resume.py' to continue.`
- **Handoff Logic**: `bin/harness_resume.py` is minted by the engine. It reads the manifest and primes the next session's context via the `UserPromptSubmit` hook.

### Task 2.4: The Loop Circuit Breaker
- **Hook**: `circuit_breaker.py` (`PostToolUseFailure`)
- **Action**: Tracks consecutive failed tool exits. If failures >= 3, return **`exit 2`** to force a strategic pivot.

### Task 2.5: Shadow Task Tracker (Token Efficiency)
- **Goal**: Minimize prose and maximize token efficiency by moving task state out-of-band.
- **Mechanism**: Mint `bin/task_tracker.py`.
- **Sync Logic**: `task_tracker.py --sync-current-progress` automatically uses `git diff --stat` and `git status --porcelain` to update progress in `campaign_state.json` (avoiding raw diff token bombs). 
- **Zero-Prose Mandate**: Update agent templates to replace verbose summaries with a single call to `task_tracker.py`. The next agent reads the JSON state (cheap) instead of the previous agent's chat history (expensive).

---

## Phase 3: The Contract-Based Verification Engine
**Timeline**: Week 3

### Task 3.1: Mint Deterministic Verification Spec
- Generate a `verify_contract.py` script into the target workspace's `scripts/`.
- This script reads a `verification_contract.json` (the Deterministic Verification Spec) which defines pass/fail assertions.

### Task 3.2: Capped Evaluator Hook
- **Hook**: `contract_evaluator.py` (Bound to `Stop` or `PostToolUse` for file writes).
- **Action**: To solve Evaluator Conflict of Interest, this Python hook intercepts the workflow and runs deterministic checks.
- **Mechanism**: 
  1. It executes `verify_contract.py`.
  2. It performs **File Assertions** (exists, content match, regex check).
  3. It performs **Linter/Build Checks** (invoking project-native tools).
  4. **Capped Output**: Captures max 100 lines / 10KB of output. If output exceeds caps, provides summarized stderr/stdout to prevent context erasure.
  5. If ANY check fails, it returns **`exit 2`** and blocks the session exit, piping the summarized failure report back to the main agent. 

---

## Phase 4: Observability & Langfuse Integration
**Timeline**: Month 2+

### Task 4.1: Asynchronous Langfuse Telemetry
- **Action**: Mint a `langfuse_wrapper.py` injected into all `PostToolUse` events. 
- Captures latency, cost, and routing accuracy asynchronously.
- **Mandate**: Before any hook forcefully exits the session (e.g., `sys.exit(2)`), it must explicitly call `langfuse.flush()` to ensure synchronous telemetry delivery and prevent data loss.

### Task 4.2: Cascading Context Generation
- Modify the minting engine to structure context hierarchically (Repository -> Standards -> Domain -> Campaign -> Task).

---

## Phase 5: Acceptance Metrics
**Benchmark**:
- **Branch D Speed**: Surgical edits must not trigger planner/verifier subagents.
- **Token Efficiency**: Standard feature paths must show >30% reduction in prompt word count.
- **Verification Safety**: Failed verification feedback must stay under 2,000 characters.
- **Robustness**: 0% state corruption incidents across 100 simulated forced-exits.archically (Repository -> Standards -> Domain -> Campaign -> Task).

---

## Phase 5: Acceptance Metrics
**Benchmark**:
- **Branch D Speed**: Surgical edits must not trigger planner/verifier subagents.
- **Token Efficiency**: Standard feature paths must show >30% reduction in prompt word count.
- **Verification Safety**: Failed verification feedback must stay under 2,000 characters.
- **Robustness**: 0% state corruption incidents across 100 simulated forced-exits.ailed verification feedback must stay under 2,000 characters.
- **Robustness**: 0% state corruption incidents across 100 simulated forced-exits. 2,000 characters.
- **Robustness**: 0% state corruption incidents across 100 simulated forced-exits.ed-exits.