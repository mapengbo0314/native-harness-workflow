# Harness Document & State Management

The Harness architecture uses a simplified, LLM-native approach to tracking tasks and architectural designs. We do NOT use JSON files or moving file scripts. Instead, we rely entirely on Markdown frontmatter and checklists.

## Folder Structure
- `docs/designs/`: Stores the primary architectural specifications and problem statements.
- `docs/designs/`: Stores the checklists and task-tracking documents for in-flight implementations.

## Document Lifecycle

### 1. Proposed (Planner Phase)
When a new design is drafted, the Planner creates `docs/designs/{design-name}.md` and places the following YAML frontmatter at the top:
```yaml
---
Status: Proposed
Created: YYYY-MM-DD
---
```

### 2. In Progress (Implementer Phase)
When the Implementer begins executing the design:
1. They edit the design doc's frontmatter to `Status: In Progress` and add `Started: YYYY-MM-DD`.
2. They create a companion progress tracking document: `docs/designs/{design-name}-progress.md`.

**Progress Doc Structure:**
```markdown
---
Status: In Progress
---
# Progress Tracking

## Completed
- [x] Initial setup

## In Progress
- [ ] Core implementation

## Blockers
(Any issues that require a review or halt execution)
```

### 3. Completed (Verifier/Reviewer Phase)
Once the code passes tests and reviews, the Verifier or Reviewer marks the task as completed:
1. Updates the frontmatter in `docs/designs/{design-name}.md` to `Status: Completed`.
2. Updates the frontmatter in `docs/designs/{design-name}-progress.md` to `Status: Completed`.

Both files simply remain in their respective directories. You do not need to move them to an archive folder.

### On Failure
If verification fails, the Reviewer/Verifier does NOT change the status. Instead, they append their findings to the `## Current Blockers` section in the progress document so the Implementer can read them and retry.