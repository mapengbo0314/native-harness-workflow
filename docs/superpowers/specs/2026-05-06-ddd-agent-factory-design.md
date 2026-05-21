# Design Document: DDD Agent Factory Integration (`harness init --ddd`)

## Business Problem
Onboarding agents to a new or legacy codebase often results in "architectural drift" or "layering traps" because the agents lack deep domain knowledge and context of legacy mappings. We need a way to extract and align on a Ubiquitous Language (UL) and a Translation Map during the initial setup phase.

## Technical Plan
We will integrate a Domain-Driven Design (DDD) onboarding sequence into the `harness init` command. This will be triggered by a `--ddd` flag.

### 1. Discovery Phase (Architect)
- The `discovery_engine` will be updated to include a "DDD Discovery" step.
- The `architect` agent will use `CodeGraph` output to identify core domain entities and potential conflicts between docs and code.
- Output: A draft `ubiquitous_language.md`.

- The user answers these questions in the CLI to resolve conflicts and define business rules.
- Output: Finalized `ubiquitous_language.md` and a `translation_map.md` (Domain -> Legacy).

### 3. Minting Phase (Agent Factory)
- The `minting_engine.py` will be updated to take these DDD documents as input.
- It will inject the content of `ubiquitous_language.md` and `translation_map.md` into the `system_prompt` or a dedicated context section for all specialized agents created in the new workspace.
- **Skill Injection**: New agents will be minted with specific DDD-related skills (e.g., `ddd_alignment`, `grill_user`) that allow them to trigger the alignment flow during regular engineering tasks.

## Engineering Workflow Integration
To ensure the DDD benefits persist beyond setup, the specialized agents will:
- **Reference the UL**: All task analysis starts by checking the `ubiquitous_language.md`.
- **Trigger Alignment**: If an agent detects a domain conflict or ambiguity in a new task, it can invoke a `/grill-me` skill to clarify with the user.
- **Maintain the Map**: Agents are instructed to suggest updates to the `translation_map.md` when they discover new legacy-to-domain mappings.

## Component Changes

### `harness/cli.py`
- Add `--ddd` flag to `argparse`.
- Implement `run_ddd_grill()`: A loop that interacts with the `discovery_engine` to present and collect answers to grill questions.

### `harness/discovery_engine.py`
- `discover_ddd_context(index_data)`: New function to generate the initial UL and a list of alignment questions.
- `refine_ddd_context(answers)`: New function to synthesize answers into final UL and Translation Map.

### `harness/minting_engine.py`
- `mint_workspace()`: Update to accept `ddd_context` and write the `.md` files to the target workspace.
- Update agent template logic to include these files in the context loaded by the subagents.

## Success Criteria
- `harness init --ddd` successfully generates a workspace where agents "know" the domain language.
- The generated agents reference the Translation Map when modifying legacy code.
- The interactive grill session feels seamless within the CLI.

## Implementation Phases
1. **Phase 1**: Update `discovery_engine.py` with DDD discovery prompts.
2. **Phase 2**: Implement the interactive grill loop in `cli.py`.
3. **Phase 3**: Update `minting_engine.py` to inject DDD context into new workspaces.
4. **Phase 4**: Verification with a test project.
