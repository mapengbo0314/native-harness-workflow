# Phase 7: Compatibility Adapters - Implementation Plan

## Problem Statement
The Harness Generator logic currently has platform-specific conditional branches (e.g., `if platform_choice == "2"`, `if active_platform == "codex"`) scattered across `src/harness/cli.py` and `src/harness/minting_engine.py`. This makes it difficult to maintain and scale support for new platforms (e.g., Gemini, Codex, Cursor, Claude). We need a unified `PlatformAdapter` interface to encapsulate platform-specific behavior while preserving the Claude adapter's plugin-first architecture.

## Proposed Design
We will introduce an adapter pattern to encapsulate all platform-specific logic. 

1. **`PlatformAdapter` Interface (`src/harness/adapters/base.py`)**: 
   An Abstract Base Class (ABC) defining the contract for platform-specific behaviors:
   - `get_tool_mappings() -> dict`: Returns tool name translations (e.g., `read_file` -> `Read`).
   - `get_subagent_syntax() -> str`: Returns subagent invocation syntax (e.g., `@`, `Task tool: `, `Hand off to `).
   - `get_rules_pointer_files() -> list[str]`: Returns the pointer files to generate (e.g., `["GEMINI.md"]`).
   - `generate_plugin(project_path, project_name, ...) -> Optional[str]`: For Claude, calls `generate_orchestrator_plugin`. For others, returns `None`.
   - `configure_cli(project_path, mcps_to_install) -> None`: Handles CLI setup (e.g., `claude mcp add` vs `gemini mcp add`).
   - `get_agent_manifest_format() -> str`: Determines if agents are rendered as standalone markdown files or combined Codex YAML.

2. **Concrete Adapters (`src/harness/adapters/*.py`)**:
   - `ClaudeAdapter`: Implements plugin generation, `Task tool: ` syntax, and Claude tool mappings.
   - `GeminiAdapter`: Implements `GEMINI.md` generation and `@` syntax.
   - `CodexAdapter`: Implements `CODEX.md` generation, `Hand off to ` syntax, and YAML-based `AGENTS.md` synthesis.
   - `CursorAdapter`: Implements `.cursorrules` generation and `@` syntax.
   - `GenericAdapter`: Fallback for custom agents.

3. **Adapter Factory (`src/harness/adapters/__init__.py`)**:
   - `def get_adapter(platform_choice: str) -> PlatformAdapter`: Returns the instantiated adapter based on user choice.

4. **Refactoring Consumers**:
   - Update `src/harness/minting_engine.py` to instantiate the adapter and replace `if/else` ladders for tool replacements, agent syntax, and pointer files.
   - Update `src/harness/cli.py` to use `adapter.configure_cli()` and `adapter.generate_plugin()` instead of inline conditions.

## Alternatives
- **Configuration Dictionary**: Instead of OOP adapters, use a large `PLATFORMS` dictionary. *Rejected* because plugin generation and CLI configuration require imperative logic, not just static data.

## Sphinch Marks
- [ ] `PlatformAdapter` ABC is defined in `src/harness/adapters/base.py`.
- [ ] Factory `get_adapter` correctly resolves "1" to `GeminiAdapter`, "2" to `ClaudeAdapter`, etc.
- [ ] `minting_engine.py` relies strictly on `adapter.get_subagent_syntax()` rather than inline `if platform_choice == "2"`.
- [ ] `ClaudeAdapter` successfully calls `generate_orchestrator_plugin`.
- [ ] Test coverage exists for all adapter implementations to ensure correct configurations.

## Plan

### Step 1: Create the Adapter Interface and Base Class
- Create `src/harness/adapters/` directory with `__init__.py`.
- Define `PlatformAdapter` ABC in `src/harness/adapters/base.py`.

### Step 2: Implement Concrete Adapters
- Create `claude.py`, `gemini.py`, `codex.py`, `cursor.py`, and `generic.py` inside `src/harness/adapters/`.
- Move the platform-specific rules (tool mappings, pointer files, syntaxes) from `minting_engine.py` into the respective adapters.
- Move CLI configuration logic from `cli.py` (`_configure_optional_platform_cli`) into the respective adapters.

### Step 3: Implement Adapter Factory
- In `src/harness/adapters/__init__.py`, write the `get_adapter(platform_choice: str)` function.

### Step 4: Refactor `minting_engine.py`
- Replace `platform_map_normalized` and inline `tool_replacements` mapping logic with `adapter.get_tool_mappings()`.
- Replace `SUBAGENT_SYNTAX` inline logic with `adapter.get_subagent_syntax()`.
- Replace inline pointer file generation (`files_to_generate`) with `adapter.get_rules_pointer_files()`.
- Replace Codex `AGENTS.md` specific branching with a generic agent rendering pipeline controlled by `adapter.get_agent_manifest_format()`.

### Step 5: Refactor `cli.py`
- Replace `_configure_optional_platform_cli` with `adapter.configure_cli()`.
- Replace `should_generate_orchestrator_plugin` check with `adapter.generate_plugin()`.

## Verification
- Run `pytest tests/unit/` to ensure no regression in `minting_engine` rendering.
- Manually run `harness init` with `--llm gemini` (Choice 1) to verify Gemini adapter works without throwing errors.
- Manually run `harness init` with `--llm anthropic` (Choice 2) to verify Claude orchestrator plugin is still successfully generated.
- Ensure all Sphinch Marks pass.