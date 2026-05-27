# Documentation State Management System

This directory maintains the lifecycle of design documents and technical specifications across the agentic harness workflow. It implements a state machine that tracks document maturity from initial design through completion and archival.

## Overview: Document State Machine

Documents follow a four-state lifecycle:

1. **proposed**: Initial design document created by Planner agents. Not yet under implementation.
2. **inprogress**: Design has been picked up by Implementer agents. An active progress document tracks real-time status.
3. **completed**: Implementation finished and verified by Verifier agents. All requirements met.
4. **reference**: Archived document retained for historical reference and pattern lookup.

Valid state transitions:
- `proposed` → `inprogress` (implementation begins)
- `inprogress` → `completed` (verification passes)
- `completed` → `reference` (archival for historical tracking)

## Directory Structure

- **`proposed/`**: Design documents awaiting implementation. Planner agents create and curate designs here.
- **`inprogress/`**: Active implementations. Each in-progress item has a corresponding progress doc tracking real-time milestones.
- **`completed/`**: Finished implementations. Designs and progress docs that passed verification reside here.
- **`reference/`**: Archived documents. Historical tracking and pattern lookup; moved from completed for long-term storage.
- **`manifest.json`**: Central registry of all documents and their lifecycle state. Single source of truth for document metadata.

## For Planner Agents

### Before Creating a Design

1. Check `docs/manifest.json` to ensure your design doesn't duplicate existing work.
2. Verify the design is not already in `proposed/`, `inprogress/`, or `completed/` states.

### After Design Completion

1. Place the design document in `docs/proposed/{design_name}.md`.
2. Add an entry to `docs/manifest.json` with state `proposed`.

### Example Manifest Entry (Proposed)

```json
{
  "name": "api-v2-design",
  "state": "proposed",
  "created_date": "2026-05-26T14:30:00Z",
  "inprogress_since": null,
  "progress_doc_path": null,
  "description": "RESTful API v2 with async endpoints and WebSocket support"
}
```

## For Implementer Agents

### Upon Starting Implementation

1. Move the design from `docs/proposed/{design_name}.md` to `docs/inprogress/{design_name}.md`.
2. Create a **progress document** at `docs/inprogress/{design_name}-progress.md`.
3. Update `docs/manifest.json`:
   - Change state from `proposed` to `inprogress`
   - Set `inprogress_since` to current ISO8601 timestamp
   - Set `progress_doc_path` to `inprogress/{design_name}-progress.md`

### Progress Document Template

The progress document mirrors the design structure and tracks implementation status:

```markdown
# {Design Name} — Progress Tracker

**Design Document**: `inprogress/{design_name}.md`  
**Status**: In Progress  
**Started**: 2026-05-26T14:30:00Z  
**Last Updated**: 2026-05-26T16:45:00Z

## Completed Sections

- [x] Component A: Database schema
- [x] Component B: API endpoints
- [ ] Component C: Authentication layer
- [ ] Component D: Deployment pipeline

## Current Blockers

- Waiting for security team review on authentication approach
- Need clarification on database indexing strategy

## Remaining Work

1. Implement authentication with OAuth 2.0
2. Add API rate limiting
3. Write integration tests
4. Performance profiling

## Milestones

- Milestone 1: Core functionality (EST: 2026-05-30) — NOT STARTED
- Milestone 2: Testing & verification (EST: 2026-06-06) — NOT STARTED
- Milestone 3: Deployment (EST: 2026-06-13) — NOT STARTED

## Notes

[Any context about challenges, decisions, or deviations from the original design]
```

### Why Progress Documents?

Progress documents externalize implementation context. If a context reset occurs (new Implementer session), the progress doc allows seamless resumption without re-reading the full design. Update this document as sections complete and blockers emerge.

## For Verifier Agents

### Verification Workflow

1. **Read the design spec** from `docs/inprogress/{design_name}.md`.
2. **Review the progress document** at `docs/inprogress/{design_name}-progress.md`.
3. **Compare requirements against completion**:
   - Verify all design sections are marked complete in progress doc
   - Confirm implementation adheres to specification
   - Check that no blockers remain unresolved

### On PASS: State Transition to Completed

1. Move design from `docs/inprogress/{design_name}.md` to `docs/completed/{design_name}.md`.
2. Move progress doc from `docs/inprogress/{design_name}-progress.md` to `docs/reference/{design_name}-progress.md`.
3. Update `docs/manifest.json`:
   - Change state from `inprogress` to `completed`
   - Keep `inprogress_since` (immutable timestamp for history)
   - Update `progress_doc_path` to `reference/{design_name}-progress.md`

### On FAIL: Escalate to Implementer

If verification fails, document blockers in the progress doc and return to Implementer with specific gaps. Do not mark as completed.

### Example Manifest Entry (Completed)

```json
{
  "name": "api-v2-design",
  "state": "completed",
  "created_date": "2026-05-26T14:30:00Z",
  "inprogress_since": "2026-05-26T15:00:00Z",
  "progress_doc_path": "reference/api-v2-design-progress.md",
  "description": "RESTful API v2 with async endpoints and WebSocket support"
}
```

## Manifest Schema

The `manifest.json` file is the central registry of all documents. Each entry has the following schema:

### Full Schema

```json
{
  "docs": [
    {
      "name": "string (unique document identifier, e.g., 'api-v2-design')",
      "state": "proposed | inprogress | completed | reference",
      "created_date": "ISO8601 timestamp (when design was created)",
      "inprogress_since": "ISO8601 timestamp or null (when implementation started)",
      "progress_doc_path": "string path or null (path to inprogress/{name}-progress.md)",
      "description": "string (one-line summary of design)"
    }
  ]
}
```

### Field Descriptions

- **name**: Unique identifier for the document. Use kebab-case (e.g., `oauth2-integration`, `db-migration-v3`).
- **state**: Current lifecycle state. Must be one of: `proposed`, `inprogress`, `completed`, `reference`.
- **created_date**: ISO8601 timestamp when Planner created the design. Never changes.
- **inprogress_since**: ISO8601 timestamp when Implementer moved design to inprogress. Null until state changes from proposed. Never changes once set.
- **progress_doc_path**: Path to the progress tracking document (relative to `docs/`). Null until implementation starts. Updated when state transitions.
- **description**: One-line summary (max 80 characters). Use this in logs and dashboards.

### Manifest Examples

#### All States

```json
{
  "docs": [
    {
      "name": "proposed-feature-x",
      "state": "proposed",
      "created_date": "2026-05-26T14:30:00Z",
      "inprogress_since": null,
      "progress_doc_path": null,
      "description": "New feature for user analytics dashboard"
    },
    {
      "name": "api-v2-refactor",
      "state": "inprogress",
      "created_date": "2026-05-20T10:00:00Z",
      "inprogress_since": "2026-05-25T09:30:00Z",
      "progress_doc_path": "inprogress/api-v2-refactor-progress.md",
      "description": "Refactor API layer for improved performance and testability"
    },
    {
      "name": "auth-oauth2",
      "state": "completed",
      "created_date": "2026-04-15T13:20:00Z",
      "inprogress_since": "2026-04-20T08:00:00Z",
      "progress_doc_path": "reference/auth-oauth2-progress.md",
      "description": "OAuth 2.0 integration for third-party apps"
    },
    {
      "name": "db-migration-v1",
      "state": "reference",
      "created_date": "2026-03-01T11:00:00Z",
      "inprogress_since": "2026-03-05T09:00:00Z",
      "progress_doc_path": "reference/db-migration-v1-progress.md",
      "description": "Database schema migration for multi-tenancy"
    }
  ]
}
```

## Workflow Integration Points

### Planner Agent Checklist

- [ ] Check `manifest.json` for duplicates
- [ ] Create design in `proposed/`
- [ ] Add entry to `manifest.json` with state=proposed
- [ ] Include design rationale and requirements

### Implementer Agent Checklist

- [ ] Read design from `proposed/`
- [ ] Move design to `inprogress/`
- [ ] Create progress doc at `inprogress/{name}-progress.md`
- [ ] Update `manifest.json` (state, inprogress_since, progress_doc_path)
- [ ] Implement per design specification
- [ ] Update progress doc with milestones as work progresses

### Verifier Agent Checklist

- [ ] Read design from `inprogress/`
- [ ] Review progress doc to verify all sections complete
- [ ] Test implementation against specification
- [ ] On PASS: Move files and update `manifest.json` (state=completed)
- [ ] On FAIL: Document blockers in progress doc and escalate

## Best Practices

1. **Keep descriptions concise**: One line, max 80 characters. Use for logs and summaries.
2. **Use consistent naming**: Kebab-case for document names (e.g., `feature-x-design`, `bug-fix-auth`).
3. **Update progress docs frequently**: This is your context resumption lifeline.
4. **Immutable timestamps**: created_date and inprogress_since never change once set.
5. **Archive aggressively**: Move completed docs to reference/ to keep inprogress/ clean.
6. **Check manifest first**: Always consult manifest.json before starting work to avoid duplication.
