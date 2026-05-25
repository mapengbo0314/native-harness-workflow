# Phase 7: Compatibility Adapters - Implementation Plan

## Problem Statement
The Harness Generator logic currently has platform-specific conditional branches (e.g., `if platform_choice == "2"`, `if active_platform == "codex"`) scattered across `src/harness/cli.py` and `src/harness/minting_engine.py`. This makes it difficult to maintain and scale support for new platforms (e.g., Gemini, Codex, Cursor, Claude). We need a unified `PlatformAdapter` interface to encapsulate platform-specific behavior while ensuring all platforms receive the necessary core infrastructure (hooks, state, contracts, skills).

## Proposed Design
We will introduce an adapter pattern to encapsulate all platform-specific logic. 

1. **`PlatformAdapter` Interface (`src/harness/adapters/base.py`)**: 
   An Abstract Base Class (ABC) defining the contract for platform-specific behaviors:
   - `get_platform_name() -> str`: Returns the nominal string (e.g., `"gemini"`, `"claude"`).
   - `get_config_dir_name() -> str`: Returns the global config directory (e.g., `".gemini"`, `".claude"`).
   - `get_plugin_env_var_name() -> str`: Returns the env var prefix for hook templating (e.g., `"GEMINI_PLUGIN_ROOT"`).
   - `get_tool_mappings() -> dict`: Returns tool name translations (e.g., `read_file` -> `Read`).
   - `get_subagent_syntax() -> str`: Returns subagent invocation syntax (e.g., `@`, `Task tool: `).
   - `format_subagent_prompt(task_desc: str) -> str`: Formats the payload/prompt for the subagent, acknowledging different platforms require different structures (inline vs JSON).
   - `get_rules_pointer_files() -> list[str]`: Returns the pointer files to generate (e.g., `["GEMINI.md"]`).
   - `get_hook_directory() -> str`: Returns the platform-specific directory for hooks (e.g., `.gemini/hooks`).
   - `install_hooks(project_path: Path) -> None`: Handles templating and placement of pre/post execution hooks. It MUST dynamically rewrite variables like `${CLAUDE_PLUGIN_ROOT}` and direct `.claude/` path references based on the platform.
   - `generate_core_infrastructure(project_path: Path) -> None`: Guarantees the generation of required state, contracts, and skills directories for ALL platforms, rather than just Claude.
   - `configure_cli(project_path, mcps_to_install) -> None`: Handles CLI setup (e.g., `claude mcp add` vs `gemini mcp add`).
   - `get_agent_manifest_format() -> str`: Determines if agents are rendered as standalone markdown files or combined Codex YAML.

2. **Concrete Adapters (`src/harness/adapters/*.py`)**:
   - `ClaudeAdapter`: Implements `Task tool: ` syntax, Claude tool mappings, and installs hooks to `.claude/hooks` using `CLAUDE_PLUGIN_ROOT`.
   - `GeminiAdapter`: Implements `GEMINI.md` generation, `@` syntax, and installs hooks to `.gemini/hooks` using `GEMINI_PLUGIN_ROOT`.
   - `CodexAdapter`: Implements `CODEX.md` generation, `Hand off to ` syntax, YAML-based `AGENTS.md` synthesis, and installs hooks to `.codex/hooks`.
   - `CursorAdapter`: Implements `.cursorrules` generation, `@` syntax, and installs hooks to `.cursor/hooks`.
   - `GenericAdapter`: Fallback for custom agents (no hooks installed by default).

3. **Adapter Factory (`src/harness/adapters/__init__.py`)**:
   - `def get_adapter(platform_id: str) -> PlatformAdapter`: Returns the instantiated adapter based on a logical identifier (e.g., `"gemini"`, `"claude"`), decoupled from CLI menu choices.

4. **Refactoring Consumers**:
   - Update `src/harness/minting_engine.py` to instantiate the adapter and replace `if/else` ladders. Remove obsolete `should_generate_orchestrator_plugin`.
   - Update `src/harness/cli.py` to map menu choices to logical `platform_id`s, then use `adapter.configure_cli()` and `adapter.generate_core_infrastructure()`.

## Alternatives
- **Configuration Dictionary**: Instead of OOP adapters, use a large `PLATFORMS` dictionary. *Rejected* because hook templating, plugin infrastructure generation, and CLI configuration require imperative logic, not just static data.

## Sphinch Marks
- [ ] `PlatformAdapter` ABC is defined in `src/harness/adapters/base.py` including `install_hooks()`, `get_platform_name()`, and `get_config_dir_name()`.
- [ ] Factory `get_adapter` resolves logical identifiers like `"gemini"` (not CLI indexes like `"1"`).
- [ ] `minting_engine.py` relies strictly on `adapter.get_subagent_syntax()` and `adapter.format_subagent_prompt()` rather than inline conditionals.
- [ ] Obsolete function `should_generate_orchestrator_plugin` is entirely removed from `minting_engine.py`.
- [ ] `adapter.install_hooks()` successfully templates hook files (replacing `${CLAUDE_PLUGIN_ROOT}` and `.claude` paths) for the target platform.
- [ ] `adapter.generate_core_infrastructure()` provisions state, contracts, and skills for all platforms.
- [ ] Unit tests (e.g., `test_cli.py`, `test_minting_engine.py`) are updated to mock `get_adapter` and verify adapter delegation.

## Plan

### Step 1: Create the Adapter Interface and Base Class
- Create `src/harness/adapters/` directory with `__init__.py`.
- Define `PlatformAdapter` ABC in `src/harness/adapters/base.py` with the complete contract.

### Step 2: Implement Concrete Adapters
- Create `claude.py`, `gemini.py`, `codex.py`, `cursor.py`, and `generic.py` inside `src/harness/adapters/`.
- Move the platform-specific rules (tool mappings, pointer files, syntaxes) into the respective adapters.
- Move CLI configuration logic into the adapters.
- Implement templating logic within `install_hooks()` for each adapter or the base class to dynamically replace environment variables.

### Step 3: Implement Adapter Factory
- In `src/harness/adapters/__init__.py`, write the `get_adapter(platform_id: str)` function.

### Step 4: Refactor `minting_engine.py`
- Replace `platform_map_normalized` and inline mapping logic with `adapter.get_tool_mappings()`.
- Replace `SUBAGENT_SYNTAX` inline logic with `adapter.get_subagent_syntax()` and `adapter.format_subagent_prompt()`.
- Replace inline pointer file generation with `adapter.get_rules_pointer_files()`.
- Replace Codex `AGENTS.md` specific branching with a generic agent rendering pipeline controlled by `adapter.get_agent_manifest_format()`.
- Remove `should_generate_orchestrator_plugin` from the module completely.

### Step 5: Refactor `cli.py`
- Map user menu selection to a logical `platform_id` (e.g., "1" -> "gemini").
- Replace `_configure_optional_platform_cli` with `adapter.configure_cli()`.
- Ensure hook installation logic delegates to `adapter.install_hooks()`.
- Call `adapter.generate_core_infrastructure()` to provision common harness assets (state, contracts, skills) for all platforms.

### Step 6: Refactor Tests
- Update unit tests (`test_cli.py`, `test_minting_engine.py`) to mock `get_adapter` and verify adapter delegation. Fix any tests that break due to hardcoded `.claude` path expectations.

## Verification
- Run `pytest tests/unit/` to ensure no regression in `minting_engine` rendering and that adapter routing works.
- Manually run `harness init` with `--llm gemini` to verify Gemini adapter works, generates `.gemini/hooks` with correct env vars, and provisions skills/state correctly.
- Ensure all Sphinch Marks pass.