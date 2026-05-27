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

1.  **Read Strategy**: Read `.gemini/strategy.json` to understand the verification requirements for this project.
2.  **Identify Critical Stages**: Identify all stages marked as 'critical' in the strategy.
3.  **Execute Verification**: Dispatch `@verifier` to execute all identified critical stages.
4.  **Review QA Report**: Ensure that `docs/reference/QA_REPORT.md` (or the project's equivalent QA report) contains empirical evidence of a PASS for all critical stages.
5.  **Extract Metadata**: If verification fails, you MUST extract the JSON from the `<QA_METADATA>` block in `QA_REPORT.md` and present it to the Orchestrator.

## Red Flags

-   Finalizing a task without a recent QA report.
-   Ignoring failed 'critical' stages.
-   Accepting "it should work" instead of empirical proof.