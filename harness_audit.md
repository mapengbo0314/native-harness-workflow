# 🔴 Adversarial Harness Audit: E2G Harness Generator (Minting Engine)

> **Auditor Persona**: Adversary mode — hyper-skeptical, zero flattery, evidence-based.
> **Date**: 2026-05-23
> **Scope**: Full structural analysis of the `src/harness/` Python minting framework, its templates, and the current "Deterministic Plugin Hooks Design (V4)" — compared against external harness systems.

---

## Executive Verdict

> [!CAUTION]
> Your framework generator is on the right path by pivoting to a **Minting Engine**, and your V4 Hook Design is extremely ambitious. However, the templates themselves suffer from structural rot, and the hook design relies on "Cooperative Agent" assumptions that break under real-world token pressure. To reach Level 5, the generator must mint highly optimized, token-efficient configurations tailored perfectly to the selected platform (`.claude` for Claude Code, `.gemini` for Gemini CLI), while standardizing on **Deterministic Verification Specs** rather than LLM prose.

### Maturity Score: Seth Gammon's 5 Levels

| Level | Description | Your Status |
|-------|-------------|-------------|
| **1. Raw Prompting** | Direct interaction, no persistence | ✅ Past this |
| **2. Project Context** | Persistent `CLAUDE.md`/`AGENTS.md` with background | ✅ Solid here |
| **3. Skills** | Modular, reusable workflow protocols | ⚠️ Templates exist, but are bloated and over-agented |
| **4. Hooks & Automation** | Automated quality gates, lifecycle hooks | ⚠️ V4 Design exists, but needs refinement for token efficiency |
| **5. Observability & Routing** | Telemetry, dynamic evaluation paths | ❌ **Missing Langfuse integration & deterministic evaluation paths** |

---

## Evaluation of Current Hooks (V4 Design)

I have reviewed your `2026-05-20-deterministic-plugin-hooks-design.md`. Your instinct to build a "Straightjacket" using Native Python Guardrails aligns perfectly with **Chachamaru127's** approach. However, there are gaps when compared to the broader ecosystem:

### What You Got Right (The Good)
*   **Matrix Routing (UPS Hook):** Intercepting the prompt to forcefully classify intent (Branches A/B/C/D) is a brilliant way to prevent the Orchestrator from wasting tokens "thinking" about what to do.
*   **The PreToolUse Firewall:** Blocking the Orchestrator from writing code natively enforces the Hub-and-Spoke model.
*   **Stop Hook (Verification Guardrail):** Preventing session exit until a QA report is generated is excellent practice.

### Where the Hooks Fail (The Bad)
*   **Gap #1: The "Cooperative Agent" Assumption:** The V4 design explicitly states: *"We assume a 'cooperative agent' model... strict security is not possible."* This fails the adversarial test. If the AI hallucinates or gets stuck, it will try to overwrite `.harness_state.json`. You must generate hooks that treat the AI as a chaotic actor.
*   **Gap #2: Incorrect Blocking Protocol:** The design uses `exit 1` to block. In Claude Code, `exit 1` is treated as a hook error; only **`exit 2`** correctly blocks the action and provides feedback to the agent.
*   **Gap #3: Evaluator Conflict of Interest:** Your Stop Hook forces the `@verifier` to check the work, but does not enforce **Fresh Context**. Relying on a second LLM API call (Two-Man Rule) is slow and costly; a **Contract-Based Verification Engine** is required for speed and determinism.
*   **Gap #4: Lack of Observability:** The V4 design logs to a local `.log` file. *Langfuse* and *Ruflo* prove that to optimize tokens, you need structured traces (cost, latency, tool error rates) to know *why* the agent is failing.

---

## The 20 Critical Gaps in the Templates

### Gap #5: 🔴 Platform-Targeted Generation
The minting engine must recognize the target platform. If the user selects Gemini CLI, it should generate `.gemini/` with the required templates. If the user selects Claude Code, it should generate `.claude/` containing *both* the templates AND the V4 execution hooks.

### Gap #6: 🔴 No Persistence Layer Minted
The minting engine fails to generate cross-session memory mechanisms (e.g., `campaign_state.json` or `handoff_note.md`).

### Gap #7: 🔴 Non-Deterministic Validation (The "Sphinch" Problem)
Your verification relies on LLM judgment. Validation must be deterministic. The generator needs to mint a **Verification Contract Engine** that tests against a **Deterministic Verification Spec** (`spec.json`).

### Gap #8: 🟠 Structural Rot in Templates
- `implementer.md` has a duplicated `Customization` block.
- `agent.json` references `dispatch_rules.md` — which doesn't exist.

### Gap #9: 🟠 The "Two-Man Rule" Fallacy
Relying on a second model to "grade" the first is over-engineered and costly. Better to use metadata-driven checkers (`grep`, `pytest`, `json_schema`).

### Gap #10: 🟡 No Circuit Breakers
The minted harness needs a hook script to track consecutive tool failures (e.g., 3 syntax errors in a row) and `exit 2` to prevent runaway token burn.

### Gap #11: 🟡 Context Cascading Is Flat
Context should be tiered (Repository -> Standards -> Domain), not dumped flat into the Orchestrator.

### Gap #12: 🟡 Skills Are Prose, Not Executable
Skills in `templates/boilerplate/skills/` lack machine-readable YAML workflow definitions (`allowed-tools` restrictions).

### Gap #13: 🟡 Over-Agented (The God-Harness Problem)
You have 10+ agent definitions. This increases "Context Tax," though current requirements mandate keeping this specialization.

### Gap #14: 🟠 Phantom Agent References
`orchestrator.md` references `@architect` — but `architect.md` doesn't exist.

### Gap #15: 🟠 Phantom Skill References
Agents reference non-existent skills (`pocock-tdd`, `qa-reviewer`, etc.).

### Gap #16: 🟠 Missing Rule File References
Agents include `@../rules/indexer_mandate.md` — which doesn't exist.

### Gap #17: 🟡 MCP Tool Name Inconsistency
Frontmatter lists `mcp_codegraph_codegraph_node`, but prose uses `codegraph_explore`.

### Gap #18: 🟡 JSON Hook Parsing
Hook scripts must parse stdin as structured JSON rather than using fragile regex on the hook envelope.

### Gap #19: 🟡 DDD Context Is Acknowledged-Stale
`ddd_context.json` has an overloaded "Context" term.

### Gap #20: 🟡 Malformed Skill Files
`fastapi/SKILL.md` and `nextjs/SKILL.md` lack YAML frontmatter.

---

## Actionable Strategy: World-Class Minting

1.  **Platform-Specific Payloads:** The `minting_engine.py` will generate the payload into the requested directory (`.claude/` or `.gemini/`).
2.  **Enhance the V4 Hooks:** Upgrade the current hook design by using `exit 2` for all blocks, strict circuit breaking, and atomic writes for state files.
3.  **Standardize Evaluation:** Mint a **Contract-Based Verification Engine** to enforce Spec-Driven Development, using deterministic checkers instead of LLM committees.
4.  **Shadow Task Tracking & ykdojo Handoff**: 
    - Implement a `task_tracker.py` that syncs state to `tasks.json` to eliminate verbose LLM status reports.
    - Standardize `HANDOFF.md` on the `Goal/Worked/Failed/NextSteps` schema to ensure continuity across context cutoffs.
5.  **Template Hygiene:** Address phantom references while preserving the requested agent specialization.