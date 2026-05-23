---
name: verification-before-completion
description: Use before finalizing any task to ensure all critical verification stages have passed.
---

# Verification Before Completion

You MUST NOT finalize a task or declare it complete until all critical verification stages defined for this project have passed.

## Steps

1.  **Read Strategy**: Read `<!--$HARNESS_DIR$-->/strategy.json` to understand the verification requirements for this project.
2.  **Identify Critical Stages**: Identify all stages marked as 'critical' in the strategy.
3.  **Execute Verification**: Dispatch `<!--$SUBAGENT_SYNTAX$-->verifier` to execute all identified critical stages.
4.  **Review QA Report**: Ensure that `<!--$HARNESS_DIR$-->/artifacts/QA_REPORT.md` (or the project's equivalent QA report) contains empirical evidence of a PASS for all critical stages.

## Red Flags

-   Finalizing a task without a recent QA report.
-   Ignoring failed 'critical' stages.
-   Accepting "it should work" instead of empirical proof.
