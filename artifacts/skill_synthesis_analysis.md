# Analysis: Agentic Design Protocol (ADP)
## The Synthesis of Superpowers & Design-as-Code

This document outlines the architectural convergence of the **Superpowers** workflow and the **Design-as-Code** rigor. The goal is to create a unified protocol that leverages the interactive strength of Superpowers while enforcing the technical discipline of Design-as-Code, utilizing **Grill-Me** and **Grill-with-Docs** as mandatory human-in-the-loop gates.

---

### 1. The Cross-Section Map

| Phase | Superpowers (Dialogue) | Design-as-Code (Rigor) | **ADP Integration (The Reinforcement)** |
| :--- | :--- | :--- | :--- |
| **I. Discovery** | Context exploration & visual offer. | "Peanuts and Hay" model building. | **Reinforcement**: `mcp_codegraph` context loading + mandatory `grill-with-docs` to align with existing ADRs/Domain logic. |
| **II. Challenge** | Clarifying questions. | Mandatory pushback & alternatives. | **Human-in-the-Loop**: Invoke `grill-me` here. The agent *must* try to break the user's idea before accepting it. |
| **III. Drafting** | Whole-spec proposal. | Section-by-section approval. | **Iterative Drafting**: Generate sections (Problem, Plan, Alternatives, Impl) with approval gates for each. |
| **IV. Validation** | Self-review. | Goldfish Protocol (Subagents). | **The Gauntlet**: Dispatch `@adversary` and `@verifier`. Results are reviewed by the user before implementation. |
| **V. Handoff** | `writing-plans`. | `@implementer` dispatch. | **Mean Implementation**: Plan -> TDD -> Mean Review (`@reviewer` tears it to shreds). |

---

### 2. Reinforcement Points (Human-in-the-Loop)

#### A. The "Domain Grill" (Phase I)
*   **Integration**: After initial discovery, use `grill-with-docs`.
*   **Purpose**: Ensures the proposed idea doesn't violate the **Ubiquitous Language** or established architectural patterns found in `CONTEXT.md` or `ARCHITECTURE.md`.
*   **Outcome**: A "Domain Alignment Report" that informs the technical proposal.

#### B. The "Skeptic's Grill" (Phase II)
*   **Integration**: Before writing a single line of the Design Doc, use `grill-me`.
*   **Purpose**: To force the user to defend the "Why". 
*   **Instruction**: "I have understood the 'What'. Now, I will grill you on the 'Why' and the edge cases. We will not proceed to the Design Doc until I have failed to find a fatal flaw in the logic."

---

### 3. Implementation Plan: Localization & Cleanup

1.  **Localization Path**: Move/Copy skills to `.gemini/skills/local-superpowers/`.
2.  **ADP Definition**: Create `.gemini/skills/agentic-design/SKILL.md` as the master orchestrator.
3.  **Registry Hijack**: Update `.gemini/skills.json` to point `brainstorming`, `writing-plans`, and `design-as-code` to the local versions.
4.  **Extension Removal**: Instruct the user to disable/remove the global superpower extension or ignore it via `.geminiignore` logic to prevent name collisions.
5.  **Orchestrator Update**: Rewrite `.gemini/orchestrator.md` to enforce the ADP 5-Gate lifecycle.

---

### 4. Why This Wins
*   **Context Efficiency**: Localization keeps the skill context "near" the code it manages.
*   **High Rigor**: Goldfish validation prevents the "lazy agent" syndrome where the implementer blindly follows a bad plan.
*   **User Sovereignty**: `grill-me` ensures the human remains the ultimate architect while the agent acts as the critical engineer.
