# Document State Tracking System

## Overview

This directory implements a document state machine to track the lifecycle of design documents from conception through completion and archival. The state machine ensures clear visibility into what designs are proposed, in progress, completed, or archived for reference.

### Document States

The state machine defines the following states:

- **proposed**: A design document has been created by the Planner agent and is ready for implementation
- **inprogress**: The Implementer agent has started work on a design; a progress document tracks implementation status
- **completed**: The Verifier agent has validated that the implementation matches the design specification
- **reference**: A completed design has been archived for future reference and historical context

## Directory Structure

- **proposed/**: Contains new design documents awaiting implementation
- **inprogress/**: Contains design documents currently being implemented, along with progress tracking documents
- **completed/**: Contains validated designs that have been successfully implemented
- **reference/**: Contains archived designs for historical reference and lessons learned
- **manifest.json**: Central registry tracking all documents and their current state
- **README.md**: This file; documents the system and usage guidelines

## How to Use - For Planner

The Planner agent creates design documents and registers them in the manifest.

### Workflow

1. Before creating a design, check `manifest.json` to avoid duplicate work on overlapping designs
2. Create a design document and place it in the `proposed/` directory
3. Add an entry to `manifest.json` with:
   - `state`: set to `"proposed"`
   - `inprogress_since`: set to `null`
   - `progress_doc_path`: set to `null`

### Example Entry

```json
{
  "name": "feature-x",
  "state": "proposed",
  "created_date": "2026-05-26T12:00:00Z",
  "inprogress_since": null,
  "progress_doc_path": null,
  "description": "Implement feature X to support the harness system"
}
```

## How to Use - For Implementer

The Implementer agent takes proposed designs and creates progress documents to track implementation.

### Workflow

1. Select a design from the `proposed/` state in the manifest
2. Update the manifest entry:
   - Change `state` to `"inprogress"`
   - Set `inprogress_since` to the current ISO8601 timestamp
   - Set `progress_doc_path` to `inprogress/{design_name}-progress.md`
3. Create a progress document at `inprogress/{design_name}-progress.md` that:
   - Mirrors the structure of the design document
   - Tracks which sections are completed
   - Documents blockers and risks
   - Lists remaining work items
4. As milestones complete, update the progress document with:
   - Completed sections and subsections
   - Resolution of blockers
   - Updated estimates for remaining work

### Progress Document Purpose

The progress document externalizes implementation context, making it easy to resume work after context resets. It serves as the single source of truth during implementation and is reviewed by the Verifier to confirm completion.

## How to Use - For Verifier

The Verifier agent validates that implementations match their design specifications.

### Workflow

1. Review the design document in `proposed/` or `inprogress/`
2. Compare the design against the progress document in `inprogress/`
3. Verify that:
   - All design requirements are marked as completed in the progress document
   - All blockers have been resolved
   - Implementation quality matches the design intent
4. On successful verification:
   - Update the manifest entry:
     - Change `state` to `"completed"`
     - Clear `inprogress_since` (set to `null`)
   - Move the progress document from `inprogress/` to `reference/` for archival
5. On failed verification:
   - Document issues in a comment within the progress document
   - Return the entry to the Implementer with clarification

## State Transitions

The following state transitions are valid:

- **proposed → inprogress**: When the Implementer starts work on a design
- **inprogress → completed**: When the Verifier confirms implementation matches the design
- **completed → reference**: When the design is archived after a reasonable retention period

### Invalid Transitions

The following transitions are NOT allowed:
- Skipping states (e.g., proposed → completed without inprogress)
- Reverting to previous states
- Transitions outside the defined workflow

## Manifest Format

The manifest is a JSON file containing a `docs` array. Each entry in the array represents a tracked document.

### Schema

```json
{
  "docs": [
    {
      "name": "string (unique identifier for the design)",
      "state": "proposed|inprogress|completed|reference",
      "created_date": "ISO8601 timestamp (when design was created)",
      "inprogress_since": "ISO8601 timestamp or null (when implementation started)",
      "progress_doc_path": "string path or null (path to progress document during inprogress state)",
      "description": "string (one-line description of the design purpose)"
    }
  ]
}
```

### Example Manifest

```json
{
  "docs": [
    {
      "name": "feature-authentication",
      "state": "completed",
      "created_date": "2026-05-20T10:30:00Z",
      "inprogress_since": "2026-05-21T09:00:00Z",
      "progress_doc_path": "reference/feature-authentication-progress.md",
      "description": "Implement OAuth2 authentication for the system"
    },
    {
      "name": "feature-x",
      "state": "inprogress",
      "created_date": "2026-05-26T12:00:00Z",
      "inprogress_since": "2026-05-26T14:00:00Z",
      "progress_doc_path": "inprogress/feature-x-progress.md",
      "description": "Add new capability X to the system"
    },
    {
      "name": "performance-optimization",
      "state": "proposed",
      "created_date": "2026-05-26T15:00:00Z",
      "inprogress_since": null,
      "progress_doc_path": null,
      "description": "Optimize query performance for large datasets"
    }
  ]
}
```

## Notes

- All timestamps must be in ISO8601 format (e.g., `2026-05-26T12:00:00Z`)
- The `name` field must be unique across all entries
- Progress documents should be kept in sync with implementation status
- Archived references should be retained for at least one release cycle for historical context
