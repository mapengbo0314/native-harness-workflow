# Failure Report Tracking Refactor Design

## Architecture & Data Flow
When an implementation fails fundamentally, or a Reviewer/Verifier rejects the code:
1. Instead of creating a standalone `_failure_report.md` file in `docs/reference/` (which is meant for archival), the agent will append the failure details, stack traces, and required fixes directly into the "Current Blockers" or "Notes" section of the active `docs/inprogress/{design_name}-progress.md` file.
2. The design document's state in `docs/manifest.json` remains `inprogress`.
3. The agent will then halt, allowing the user or another agent to review the progress doc and resume.

## Affected Components
- **Agent Templates:** `.gemini/agents/{implementer,reviewer,verifier}.md` and their boilerplate counterparts in `src/harness/templates/boilerplate/agents/`.
- **Instruction Change:** Remove the mandate to write to `docs/reference/{design_doc}_failure_report.md`. Add the mandate to "append failure findings to the 'Current Blockers' section of `docs/inprogress/{design_name}-progress.md`".