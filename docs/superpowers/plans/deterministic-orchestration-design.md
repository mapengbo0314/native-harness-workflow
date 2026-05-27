# Deterministic Orchestration via Prompt Hooks

## 1. Problem Statement (The Core Problem)
LLM context bloat, non-deterministic routing, and the failure of prompt-based orchestrators. When orchestrator agents are built entirely on soft prompt rules, they inevitably leak context, fail to invoke subagents reliably, or get stuck in repetitive loops. Over multiple turns (e.g., the 5-turn context bloat problem), the session context window is overwhelmed by unrelated historical steps, reducing reasoning quality and violating strict architectural separation.

## 2. Proposed Design (The Solution: Deterministic Syntax Injection)
Instead of relying on an LLM to decide when and how to route, we use a deterministic Python `UserPromptSubmit` hook.
- The hook intercepts the prompt before it reaches the CLI or LLM.
- It evaluates physical artifacts in the workspace (e.g., the presence of a test file, or completed design documents) to deterministically ascertain the Current Phase/Branch of the project.
- Based on the determined state, it forcibly injects `@subagent` syntax directly into the user prompt using the `modifiedPrompt` field.

## 3. Hook Output Fields Explained
To understand how the injection works, it is important to distinguish between the two primary prompt modification vectors:
- **`modifiedPrompt`**: Changes the literal user message sent to the CLI. Because the CLI parses user messages for `@agent` syntax *before* hitting the LLM, this is the field we must mutate to achieve deterministic "Syntax Injection" routing. Injecting `@subagent` here guarantees CLI-level routing.
- **`system_prompt_extension`**: Appends instructions to the system prompt. It avoids permanent chat history bloat, but it does NOT trigger CLI-level subagent routing. It only influences the LLM's behavior within the current context. For routing to work reliably at the platform level, `modifiedPrompt` is required.

## 4. Platform Adapter Layer
The core hook logic computes a generic intent (e.g., "analyze architecture", "execute code"). A Platform Adapter Layer maps this intent to the exact syntax required by the active platform. For example, a "research" intent might map to `@codebase_investigator` for Gemini CLI versus `@architect` for Claude Code. This ensures the deterministic routing engine remains portable across different CLI environments.

## 5. Context Management (Hub-and-Spoke)
By leveraging `modifiedPrompt` for deterministic routing, we naturally enforce a Hub-and-Spoke execution model. The CLI-level interception routes the user request into a targeted, short-lived, transactional subagent session. Once the subagent finishes its scoped task, control returns to the Hub (the human or the next phase) without persisting the subagent's massive step-by-step context history. This effectively eliminates the context bloat problem and preserves the integrity of each execution phase.

## Alternatives Considered
- **Pure Prompt-based Orchestration:** Relying entirely on a master LLM agent to prompt another agent via a tool call. Rejected because LLMs often hallucinate tool calls, forget to dispatch, or fail to strictly isolate context, leading to drift.
- **Using `system_prompt_extension` for routing:** Rejected because it only influences the model's behavior. The CLI routing mechanisms trigger based on parsing the user prompt's literal string (e.g., `@agent` syntax). System extensions do not natively enforce tool-based subagent isolation at the CLI level.

## Verification Criteria
- [ ] A `UserPromptSubmit` hook script exists and intercepts CLI input.
- [ ] The hook returns a JSON payload containing the `modifiedPrompt` field.
- [ ] The `modifiedPrompt` dynamically includes the correct `@subagent` syntax based on workspace artifacts.
- [ ] Subagents are successfully dispatched via CLI parsing without an LLM "deciding" to call them.
- [ ] Context from one subagent phase does not bleed into the subsequent subagent phases (demonstrating Hub-and-Spoke).
