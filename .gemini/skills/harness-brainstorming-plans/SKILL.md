---
name: harness-brainstorming-plans
description: You MUST use this before any creative work or when you have a spec/requirements for a multi-step task, before touching code. Explores user intent, produces a 4-part deterministic design document with HITL reviews.
---
<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# Unified Brainstorming & Planning

Help turn ideas into fully formed, deterministic designs and implementation plans through a strict 4-part Human-in-the-Loop (HITL) process.

Start by understanding the current project context using the `codegraph` MCP server. Once you understand the project, you MUST guide the user through the following 4-part design process.

<HARD-GATE>
Do NOT invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have completed the 4-part HITL design process and generated the final design document. You MUST explicitly invoke the `ask_user` tool after each part to get user approval.
</HARD-GATE>

## The 4-Part HITL Design Process

You MUST write the design document interactively with the user, one section at a time. After writing each section, you MUST invoke the `ask_user` tool to present the section and wait for the user to review and correct it before moving to the next.

### Part 1: Problem Understanding
- **Prompt:** "Gemini, I want you to write a design doc for me in Markdown. Let's do it one section at a time. Start with Section Zero: A plain English description of your understanding of the business problem we are trying to solve for our user."
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
- **Prompt:** "Final section: Write an extremely detailed implementation plan. You MUST enumerate every file we are going to change or create in our codebase and the rationale for why the change is necessary. You do not need to write code yet, but list every file touched."
- **Content:** Enumerate every file to be changed/created and the rationale. Ensuring TDD test files are also considered.
- **Action for Results:** Invoke `ask_user` to present Part 4. Review and correct based on user feedback.

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

Once all 4 parts are completed and approved by the user, compile the final deterministic design document.

**Documentation:**
- Save the final document to `docs/proposed/YYYY-MM-DD-<topic>-design.md` (or the user's preferred spec location).
- Commit the design document to git.

**Self-Review:**
Before finalizing, review the document:
1. **Spec coverage:** Does the plan cover the business problem?
2. **Placeholder scan:** Any "TBD" or vague requirements? Fix them inline.
3. **Internal consistency:** Do sections contradict each other?

**Execution Handoff:**
After saving the plan, offer execution choice:
- **Subagent-Driven (recommended):** Dispatch a fresh subagent per task using `superpowers:harness-subagent-driven-development`.
- **Inline Execution:** Execute tasks using `superpowers:harness-executing-plans`.
