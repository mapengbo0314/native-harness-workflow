# Omni-Compatible Refactor Design Spec

**Status**: Draft
**Date**: 2026-05-07
**Author**: Gemini CLI

## Problem Statement
The current `CodeGraph init` flow requires the user to select a target AI platform (Gemini, Claude, etc.). This adds unnecessary friction and creates a workspace that is only optimized for one tool. Since we have implemented a pointer-based architecture (`GEMINI.md` -> `AGENTS.md`), we can now generate pointers for ALL platforms simultaneously, making the workspace "omni-compatible" out of the box.

## Proposed Changes

### 1. CLI Refactor (`harness/cli.py`)
- Remove the `platform_questions` prompt using `inquirer`.
- Remove the manual `platform_choice` input.
- Pass a unified context to the minting engine without platform-specific flags.
- Remove the conditional logic that determines the `target_dir` (always use `.agents` or a consistent root-level approach, but since pointers live in the root, the location of the `_agents` folder is secondary). We will keep `.agents` as the default for the "Brain".

### 2. Minting Engine Refactor (`harness/minting_engine.py`)
- Remove `platform_choice` from the `mint_workspace` signature.
- **Unconditional Pointer Generation**: Write `GEMINI.md`, `CLAUDE.md`, `.cursorrules`, and `.github/copilot-instructions.md` to the project root. All will contain:
  ```markdown
  # Agentic Harness
  Please read `AGENTS.md` for core repository instructions and routing rules.
  ```
- **Unconditional MCP Generation**: Write `mcp.json` to the project root and `.cursor/mcp.json`.
- **Unconditional Skill Pointer Generation**: Update the `setup_harness.sh` logic to create skill pointers for both `.claude/skills/` and `.gemini/skills/`.

### 3. Setup Script Refactor (`setup_harness.sh` generation)
- Update the bash script to auto-detect installed CLIs (`gemini`, `copilot`).
- Provide consolidated instructions for manual plugin installation (`/plugin install...`).
- Execute skill pointer generation for all platforms.

## Sphinch Marks

- [ ] **CLI Cleanliness**: `harness/cli.py` contains no `inquirer` calls related to platform selection.
- [ ] **Engine Signature**: `harness/minting_engine.py:mint_workspace` does not accept `platform_choice`.
- [ ] **Omni-Pointers**: `minting_engine.py` contains a loop or list of 4+ platform pointer files that are written unconditionally.
- [ ] **Omni-MCP**: `minting_engine.py` writes `mcp.json` to at least two locations (root and `.cursor/`).
- [ ] **Omni-Skills**: `setup_harness.sh` generation logic contains blocks for both `.claude` and `.gemini` skill pointers.
- [ ] **Auto-Detection**: `setup_harness.sh` uses `if command -v <cli>` to guard global installations.
- [ ] **DDD Preservation**: The existing DDD questionnaire and agent generation logic remains intact and is correctly integrated into the specialized agent `config.yaml`.

## Implementation Readiness Test (Phase 3)
- Does this spec clearly define how to handle the `target_dir` (the location of the boilerplate copy)? 
  - *Decision*: We will standardize on `.agents/` as the storage for the "Core Brain" to keep the root tidy, while keeping the pointers in the root.
