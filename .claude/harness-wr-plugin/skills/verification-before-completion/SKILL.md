---
name: verification-before-completion
description: Use before finalizing any task to ensure all critical verification stages have passed.
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# Verification Before Completion

You MUST NOT finalize a task or declare it complete until all critical verification stages defined for this project have passed.

## Steps

1.  **Identify Critical Stages**: Identify all critical verification stages based on the project's testing standards and guidelines.
2.  **Execute Verification**: Dispatch `Task(subagent_type="verifier")` to execute all identified critical stages.
3.  **Review QA Report**: Ensure that `.claude/docs/designs/QA_REPORT.md` (or the project's equivalent QA report) contains empirical evidence of a PASS for all critical stages.
4.  **Extract Metadata**: If verification fails, you MUST extract the JSON from the `<QA_METADATA>` block in `QA_REPORT.md` and present it to the Orchestrator.

## Red Flags

- Finalizing a task without a recent QA report.
- Ignoring failed 'critical' stages.
- Accepting "it should work" instead of empirical proof.
