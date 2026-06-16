---
name: harness-brainstorming-plans
description: You MUST use this before any creative work or when you have a spec/requirements for a multi-step task, before touching code. Explores user intent, produces a 5-part deterministic design document with HITL reviews.
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# Unified Brainstorming & Planning

Help turn ideas into fully formed, deterministic designs and implementation plans through a strict 5-part Human-in-the-Loop (HITL) process.

**First act — persist the planning phase (R2):** before anything else, run:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/session_phase.py" set-phase planning --session "<id from SYSTEM STATE>"
```

This records `phase=planning` in the session store. The search-first gate holds source writes while this phase is active until research is recorded — run the `search-first` skill (or its proportionality waiver) as part of the design work below.

Start by understanding the current project context using the `codegraph` MCP server. Once you understand the project, you MUST guide the user through the following 5-part design process.

<HARD-GATE>
Do NOT invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have completed the 5-part HITL design process and generated the final design document. You MUST explicitly invoke the `ask_user` tool after each part to get user approval.
</HARD-GATE>

## The 5-Part HITL Design Process

You MUST write the design document interactively with the user, one section at a time. After writing each section, you MUST invoke the `ask_user` tool to present the section and wait for the user to review and correct it before moving to the next. Interview the user relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

### Part 1: Problem Understanding

- **Prompt:** "Agent, I want you to write a design doc for me in Markdown. Let's do it one section at a time. Start with Section Zero: A plain English description of your understanding of the business problem we are trying to solve for our user."
- **Content:** Write a plain English description of your understanding of the business problem.
- **Action for Results:** Invoke `ask_user` to present Part 1. Review and correct based on user feedback.

### Part 2: Technical Plan

- **Prompt:** "Next, write a plain English description of the technical implementation plan. What are the big components? How will they fit together? How does the feature fit in the ecosystem? Use as little jargon as you can."
- **Content:** High-level component architecture and ecosystem fit.
- **Action for Results:** Invoke `ask_user` to present Part 2. Review and correct based on user feedback.

### Part 3: Alternatives

- **Prompt:** "Next section: Describe any alternatives we considered but ruled out during our conversation - also in plain English"
- **Content:** Describe any alternatives considered but ruled out.
- **Action for Results:** Invoke `ask_user` to present Part 3. Review and correct based on user feedback.

### Part 4: Detailed Implementation

- **Prompt:** "Next section: Write an extremely detailed implementation plan. You MUST enumerate every file we are going to change or create in our codebase and the rationale for why the change is necessary. You do not need to write code yet, but list every file touched."
- **Content:** Enumerate every file to be changed/created and the rationale. Ensuring TDD test files are also considered.
- **Action for Results:** Invoke `ask_user` to present Part 4. Review and correct based on user feedback.

### Part 5: Adversarial Review

- **Prompt:** "Final step: run the `adversary-pipeline` skill against the design. Tier 1 (default) applies Attacker/Defender/Auditor role lenses inline — minutes, no subagents. Tier 2 (opt-in, multi-subsystem designs) runs budget-enforced agent passes."
- **Content:** Run the `adversary-pipeline` skill on the saved design doc. It writes the prioritized risk report to `docs/adversary/YYYY-MM-DD-<topic>-risk-report.md` — the artifact the sign-off gate below verifies. The report must NOT edit the core design; design amendments happen as revisions with the findings cited.
- **Action for Results:** Invoke `ask_user` to present the risk report verdict (and, when the design spans multiple subsystems, whether to escalate to Tier 2). Proceed based on user feedback.

## File Structure & Granularity (High Standards)

When detailing the implementation in Part 4, strictly adhere to these standards:

- **Scope Check:** Ensure the feature is appropriately scoped. If the spec covers multiple independent subsystems, suggest breaking this into separate plans.
- **File Structure:** Design units with clear boundaries and well-defined interfaces. Each file should have one clear responsibility. Prefer smaller, focused files over large ones that do too much. Files that change together should live together. Split by responsibility, not by technical layer.
- **Exact File Paths:** Always use exact file paths (e.g., `src/path/to/file.py`, `tests/path/to/test.py`).
- **Bite-Sized Task Granularity:** Break down the implementation into bite-sized tasks. Each step is one action (2-5 minutes) such as write failing test, write minimal implementation, test, commit.
- **DRY, YAGNI, TDD:** Do Not Repeat Yourself. You Aren't Gonna Need It. Test-Driven Development is mandatory.
- **No Placeholders:** Every detail must be explicit. Do not use placeholders like "TBD", "TODO", "implement later", "add validation".
- **Code Snippets Exception:** Unlike previous workflows, you do NOT need to write out the code snippets in the plan itself. Focus on the logical steps, files, and rationales.

## After the Design

Once all 5 parts are completed and approved by the user, compile the final deterministic design document.

**Documentation:**

- Save the final document to `<!--$HARNESS_DIR$-->/docs/designs/YYYY-MM-DD-<topic>-design.md` (or the user's preferred spec location).
- Initialize a corresponding `<!--$HARNESS_DIR$-->/docs/designs/YYYY-MM-DD-<topic>-progress.md` file with the extracted tasks.
- Commit the design document to git.
- **Adversary exit gate (F2, C3 — advisory semantics, accepted in writing):** when `pipeline.dispatcher.gates.adversary_exit` is on, sign-off requires a risk report newer than the design doc. Verify deterministically before clearing the phase — if it fails, run the `adversary-pipeline` skill first:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/check_risk_report.py" "<!--$HARNESS_DIR$-->/docs/designs/YYYY-MM-DD-<topic>-design.md"
```

- **Exit the planning phase (R2):** the design sign-off clears the persisted phase, recording the design doc as the exit artifact (this releases the search-first gate):

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/session_phase.py" clear-phase --session "<id from SYSTEM STATE>" --artifact "<!--$HARNESS_DIR$-->/docs/designs/YYYY-MM-DD-<topic>-design.md"
```

**Self-Review:**
Before finalizing, review the document:

1. **Spec coverage:** Does the plan cover the business problem?
2. **Placeholder scan:** Any "TBD" or vague requirements? Fix them inline.
3. **Internal consistency:** Do sections contradict each other?

**Execution Handoff:**
After saving the plan and completing the adversarial review (required for sign-off while `pipeline.dispatcher.gates.adversary_exit` is on — see Part 5), offer execution choice:

- **Subagent-Driven (recommended):** Dispatch a fresh subagent per task using `superpowers:harness-subagent-driven-development`.
- **Inline Execution:** Execute tasks using `superpowers:harness-executing-plans`.
