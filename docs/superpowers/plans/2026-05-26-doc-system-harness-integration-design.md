# Document State Tracking System Integration Design

**Date:** 2026-05-26  
**Scope:** Integrate document lifecycle management into agentic harness  
**Status:** Design Complete (Ready for Implementation)

---

## Problem Understanding

Your agentic harness currently lacks explicit document lifecycle management. Design documents, implementation plans, and specifications exist scattered across the codebase without a clear state machine or progress tracking mechanism. This makes it hard for:

- **Hooks** to know which documents exist and what state they're in (for matrix matching/routing)
- **Planner** to have a unified view of all design artifacts
- **Implementer** to know what design they're implementing and track progress against it
- **The system overall** to externalize dynamic context (what's proposed, what's being worked on, what's completed, what's archived for reference)

**Solution:** Create a **document state machine** where designs flow through states (proposed → inprogress → completed → reference), with parallel progress tracking during inprogress phase. This becomes a first-class artifact in your harness, visible and actionable by all agents.

---

## Technical Plan

### Core Components

**1. Central Manifest Registry** (`.claude/docs/manifest.json`)
- Single source of truth for document state
- Schema: `{docs: [{name, state, created_date, inprogress_since, progress_doc_path, description}]}`
- States: `proposed`, `inprogress`, `completed`, `reference`
- Manifest-driven: hooks query this file to determine behavior deterministically

**2. File Organization** (`.claude/docs/`)
```
.claude/docs/
├── manifest.json              # Central registry
├── proposed/                  # New design ideas (not yet started)
│   ├── feature-x-design.md
│   └── ...
├── inprogress/                # Active designs + progress tracking
│   ├── feature-x-design.md
│   ├── feature-x-progress.md  # Mirrors design structure, tracks done/left
│   └── ...
├── completed/                 # Finished, awaiting archival
│   ├── feature-y-design.md
│   └── ...
└── reference/                 # Historical archive
    ├── old-feature-design.md
    └── ...
```

**3. Progress Tracking During Implementation**
- When design moves to `inprogress`, Implementer creates `{design_name}_progress.md`
- Progress doc mirrors design doc structure, tracks completed subtasks and blockers
- Updated by Implementer as milestones complete
- Prevents context loss between implementation phases
- Archived to reference/ when design completes

**4. Hook Integration** (`.claude/hooks/`)
- **doc-manifest-validator.sh**: Validates manifest.json syntax and enforces state transitions
  - Runs on pre-commit; blocks invalid transitions
  - Only allows: proposed→inprogress, inprogress→completed, completed→reference
- **doc-state-router.sh**: Queries manifest to determine routing behavior
  - Read by prompt_classifier or orchestrator for matrix branching
  - Manifest-driven: no hardcoded routing logic

**5. Agent Context Updates**
- **Planner**: Checks manifest before designing; adds entries with state=proposed
- **Implementer**: Moves design to inprogress; creates and maintains progress doc
- **Verifier**: Validates progress against design; moves to completed on PASS

---

## Alternatives Considered & Rejected

1. **Flat Directory with Filename Prefixes** (e.g., `proposed_feature-x.md`)
   - Rejected: File movements require copy-and-rename; progress docs can't co-locate; harder for hooks to pattern-match

2. **Database or YAML Registry**
   - Rejected: JSON is git-friendly, human-readable, requires no external tooling, easy for scripts to parse

3. **No Central Registry** (Hooks discover state by reading filesystem)
   - Rejected: No single source of truth; inconsistent state possible; hooks must parse directory tree

4. **Automatic State Transitions** (e.g., "test pass" → auto-move to completed)
   - Rejected (MVP): Adds complexity, requires more hook logic; better handled by agent intent for now

**Selected Approach:** Explicit manifest.json + state directories + progress tracking — provides a clean queryable registry, clear file hierarchy, and agent-driven state transitions.

---

## Detailed Implementation Plan

### A. Core Infrastructure Files (`.claude/docs/`)

**1. `.claude/docs/manifest.json` (NEW)**
- Schema: `{docs: [{name: string, state: "proposed"|"inprogress"|"completed"|"reference", created_date: ISO8601, inprogress_since: ISO8601|null, progress_doc_path: string|null, description: string}]}`
- Initialize with empty array: `{docs: []}`
- **Rationale:** Manifest-driven hooks query this file to determine behavior; queryable state without filesystem scanning

**2. `.claude/docs/README.md` (NEW)**
- System guide: how documents flow through states
- Instructions for each agent:
  - Planner: How to create a design (add to manifest with state=proposed)
  - Implementer: How to start work (move to inprogress, create progress doc)
  - Verifier: How to validate completion (compare progress vs design, move to completed)
- State transition rules and when each can happen
- **Rationale:** Onboard agents and ensure consistent usage

**3. `.claude/docs/proposed/` (NEW DIRECTORY)**
- Staging area for new design documents before implementation
- No progress tracking; no progress doc needed
- **Rationale:** Clear visual hierarchy; agents know where unvetted designs live

**4. `.claude/docs/inprogress/` (NEW DIRECTORY)**
- Active design documents + their parallel progress docs
- Each design has two files: `{name}-design.md` and `{name}-progress.md`
- **Rationale:** Co-location of spec and progress; agents know where to look for ongoing work

**5. `.claude/docs/completed/` (NEW DIRECTORY)**
- Designs that have passed verification but not yet archived
- Temporary staging before moving to reference/
- **Rationale:** Clear staging area for completion workflow

**6. `.claude/docs/reference/` (NEW DIRECTORY)**
- Historical archive of completed designs
- Only moved here after completion is verified and work is done
- **Rationale:** Keep reference materials available but out of active workflow

### B. Hook Integration (`.claude/hooks/`)

**7. `.claude/hooks/doc-manifest-validator.sh` (NEW)**
- Runs on pre-commit hook
- Validates manifest.json: valid JSON, all required fields present
- Validates state transitions: only allow proposed→inprogress, inprogress→completed, completed→reference
- Rejects commits that violate manifest integrity
- **Rationale:** Enforce consistency at commit time; prevent invalid state transitions

**8. `.claude/hooks/doc-state-router.sh` (NEW)**
- Queries manifest.json and returns routing rules for matrix branching
- Output example: `{"proposed_docs": ["feature-x"], "inprogress_docs": ["feature-y"], "completed_docs": ["feature-z"]}`
- Called by prompt_classifier or orchestrator to determine agent routing
- **Rationale:** Manifest-driven routing; hooks know which designs are in which state without hardcoded logic

### C. Agent Context Updates

**9. `.claude/agents/planner.md` (MODIFY)**
- Add instruction: "Before creating a new design, check `.claude/docs/manifest.json` for existing or similar designs"
- Add instruction: "After design spec is complete, add entry to manifest with: state=proposed, created_date=today, progress_doc_path=null"
- Add example manifest entry format
- **Rationale:** Planner is the entry point for new designs; ensures registry stays accurate

**10. `.claude/agents/implementer.md` (MODIFY)**
- Add instruction: "Upon starting implementation, read manifest.json and find design entry"
- Add instruction: "Move design state from proposed→inprogress in manifest, set inprogress_since=today"
- Add instruction: "Create `.claude/docs/inprogress/{design_name}-progress.md` mirroring design structure"
- Add instruction: "Update progress doc as milestones complete; maintain done/blockers/remaining sections"
- Add instruction: "Progress doc externalizes context; useful for pick-up after context reset"
- **Rationale:** Implementer owns progress tracking; progress doc prevents context loss

**11. `.claude/agents/verifier.md` (MODIFY)**
- Add validation step: "Read design spec and its progress doc; verify all requirements are marked complete"
- Add instruction: "On PASS: move design state from inprogress→completed in manifest"
- Add instruction: "Move progress doc from inprogress/ to reference/ for archival"
- Add instruction: "On FAIL: return to implementer with gaps identified"
- **Rationale:** Verifier gates transitions; ensures quality before marking complete

### D. Configuration

**12. `.claude/settings.json` (MODIFY)**
- Add `doc_system` config section:
  ```json
  "doc_system": {
    "enabled": true,
    "manifest_path": ".claude/docs/manifest.json",
    "hooks_dir": ".claude/hooks"
  }
  ```
- Add to `pre_commit_hooks`: `"doc-manifest-validator.sh"`
- **Rationale:** Centralize configuration; tells system where doc-system is and enables hooks

### E. Initialization (harness-wf Minting Engine)

**13. Harness-WF Minting Engine (OUT OF SCOPE for this repo)**
- The harness-wf tool should initialize doc-system directories and manifest.json when generating a Claude harness
- Create `.claude/docs/manifest.json` with empty docs array
- Create `.claude/docs/{proposed, inprogress, completed, reference}/` directories
- **Rationale:** Doc-system is built-in to harness initialization, not an add-on

---

## Implementation Sequence (Bite-Sized Tasks)

1. **Create directory structure**: `.claude/docs/{proposed,inprogress,completed,reference}/`
2. **Create manifest.json**: Initialize with empty docs array
3. **Create README.md**: System guide and agent instructions
4. **Create hook: doc-manifest-validator.sh**: Validates manifest and state transitions
5. **Create hook: doc-state-router.sh**: Queries manifest for routing decisions
6. **Update settings.json**: Add doc_system config and hook references
7. **Update planner.md**: Add manifest integration instructions
8. **Update implementer.md**: Add progress tracking instructions
9. **Update verifier.md**: Add completion validation instructions
10. **Commit**: Finalize structure and documentation
11. **Note for harness-wf**: Include doc-system initialization in minting engine for future projects

---

## How Agents Know Deterministically What to Do

**Entry Point (Planner):**
- Planner checks manifest.json for duplicate designs
- Creates design spec
- Adds entry to manifest with state=proposed

**Transition 1: proposed → inprogress (Implementer)**
- Implementer reads manifest.json, finds design entry
- Updates state to inprogress, sets inprogress_since=today
- Creates progress doc in inprogress/

**Progress Tracking (Implementer)**
- Implementer maintains progress doc during implementation
- Doc mirrors design structure: tracks completed sections and blockers
- Context is externalized; useful for context resets

**Transition 2: inprogress → completed (Verifier)**
- Verifier reads design spec and progress doc
- Validates all requirements are marked complete
- Moves design to completed state in manifest
- Archives progress doc to reference/

**Routing for Hooks:**
- Hooks call `doc-state-router.sh`
- Returns list of docs in each state
- Matrix branching can route based on state (e.g., "if design is inprogress, route to implementer")

---

## Files to Change/Create Summary

| File Path | Type | Purpose |
|-----------|------|---------|
| `.claude/docs/manifest.json` | NEW | Central registry of doc states |
| `.claude/docs/README.md` | NEW | System guide and agent instructions |
| `.claude/docs/proposed/` | NEW DIR | Staging area for new designs |
| `.claude/docs/inprogress/` | NEW DIR | Active designs + progress docs |
| `.claude/docs/completed/` | NEW DIR | Completed designs awaiting archival |
| `.claude/docs/reference/` | NEW DIR | Historical archive |
| `.claude/hooks/doc-manifest-validator.sh` | NEW | Pre-commit hook to validate manifest |
| `.claude/hooks/doc-state-router.sh` | NEW | Queries manifest for routing decisions |
| `.claude/agents/planner.md` | MODIFY | Add manifest integration |
| `.claude/agents/implementer.md` | MODIFY | Add progress tracking |
| `.claude/agents/verifier.md` | MODIFY | Add completion validation |
| `.claude/settings.json` | MODIFY | Add doc_system config and hooks |

---

## Success Criteria

- ✓ Planner can check manifest for duplicates before creating designs
- ✓ Implementer can move design to inprogress and create parallel progress doc
- ✓ Progress doc externalizes context; implementer can resume work after context reset
- ✓ Verifier can validate progress against design spec and gate completion
- ✓ Hooks enforce state transitions; invalid commits are rejected
- ✓ Hooks query manifest for routing decisions; matrix branching works
- ✓ All agents act deterministically based on manifest state
- ✓ Doc-system directories are created by harness-wf on initialization

---

**Next Step:** Dispatch to Implementer to create files and integrate hooks into settings.json and agent instructions.
