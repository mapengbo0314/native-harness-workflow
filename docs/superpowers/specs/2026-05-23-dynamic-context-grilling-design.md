# Design Doc: Dynamic LLM-Driven Context Grilling

## Problem Statement
The current initialization process of the Agentic Harness uses a static set of three generic questions to capture project context. This often fails to capture the unique domain language, business acronyms, and specific architectural invariants of a project, leading to "hallucinated" or overly generic agent identities. We need a way to dynamically analyze the codebase and "grill" the user on the specific ambiguities and core logic found in their particular project.

## Proposed Design
The "Context Grilling" loop will replace the static wizard in `src/harness/cli.py`. It will follow these steps:

1.  **Context Seeding**: Before the grilling begins, the system will generate a `technical_summary` of the project using existing functions in `discovery_engine.py` (file tree, top symbols, decorators).
2.  **LLM Question Generation**: A new function `generate_grilling_questions` will query the LLM with the `technical_summary`. The LLM is tasked with identifying 3-5 critical questions to clarify the project's domain. It must provide strictly structured "Multiple Choice Options" (e.g., "I see 'GWP'. Does it mean: A) Gross Written Premium, B) Global Web Portal, or C) Other [Please specify]?").
3.  **Interactive Terminal Loop**: The CLI will iterate through these questions using the `ask_user` tool (or its platform-specific equivalent). For each:
    *   Present the question as a multiple-choice selection, leveraging the tool's native support for options.
    *   Ensure an "Other" option is included so the user can always write a custom response if the LLM's choices are insufficient.
4.  **Context Synthesis**: Once all answers are collected, the LLM will synthesize the Q&A pair into a high-quality `CONTEXT.md` content via `synthesize_grilled_context`, ensuring it fits the required sections: Purpose, Ubiquitous Language, and Strict Invariants.
5.  **Persistence**: The resulting content is saved to `docs/domain/CONTEXT.md`.

## Alternatives
*   **Static Questions with LLM refinement**: Keep the 3 questions but use LLM to "improve" the user's answers. 
    *   *Why Rejected*: Doesn't solve the problem of missing project-specific terms (acronyms) that the LLM could have spotted in the code.
*   **Multi-turn LLM grilling**: Ask one question, get answer, send back to LLM, ask next. 
    *   *Why Rejected*: Too many API calls and high latency for a CLI tool. Generating a batch of questions is more efficient.

## Sphinch Marks
- [ ] `src/harness/discovery_engine.py` contains `generate_grilling_questions` function.
- [ ] `src/harness/discovery_engine.py` contains `synthesize_grilled_context` function.
- [ ] `src/harness/cli.py` calls `generate_grilling_questions` when `HARNESS_HEADLESS` is not "1".
- [ ] The LLM prompt for question generation explicitly asks for "multiple-choice" options, strictly avoiding open-ended questions without choices.
- [ ] The final output is saved to `docs/domain/CONTEXT.md` with sections: Purpose, Ubiquitous Language, Strict Invariants.
- [ ] `acquire_mcp_context` successfully reads the newly created `CONTEXT.md`.
- [ ] Headless mode (`HARNESS_HEADLESS=1`) bypasses the grilling loop and uses defaults.
