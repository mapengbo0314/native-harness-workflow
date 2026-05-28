# Design Document: Post-Tool-Use Deterministic Linting Hook

## 1. Problem Understanding
Currently, our subagents (`implementer` and `reviewer`) are explicitly instructed to run linters and formatters as part of their loops. This is non-deterministic, consumes tokens in the prompt, and relies on the LLM to remember to execute the correct tool for the given file type. We want to centralize and automate this enforcement by hooking into the agent's file modification actions directly. By shifting linting/formatting to a deterministic system hook, we guarantee code quality standards are applied invisibly on every write, freeing the agents to focus entirely on implementation logic.

## 2. Technical Plan
- **Hook Interception:** We will create a new Python script at `post_tool_use.py`. This script will receive the tool execution payload from the CLI for both the main agent and any subagents.
- **Action Filtering:** The script will check if `tool_name` is either `write_file`, `replace`, `Edit`, or `Write`. If it's any other tool, the hook will exit immediately to save time.
- **Filetype Routing:** For modifying tools, the hook will extract the `file_path` from the `tool_input`. Based on the file extension (e.g., `.py`), it will route to the appropriate ecosystem tools.
- **Deterministic Execution:** The hook will use Python's `subprocess` module to automatically run `ruff format <file_path>` and `ruff check --fix <file_path>` (and similarly `eslint` or `prettier` for other configured languages). 
- **Clean Up Agent Prompts:** We will remove the explicit manual linting instructions from `implementer.md` and `reviewer.md`, keeping their prompts lean and focused on logic.

## 3. Alternatives Considered
- **Agent System Prompt Enforcement**: We could keep the current approach and just write stronger prompt instructions (e.g., "You MUST run the linter"). We ruled this out because LLMs are not 100% deterministic at remembering to run commands, and it wastes tokens on repetitive instructions and execution output.
- **Git Pre-commit Hook**: We could use standard `git` pre-commit hooks to format code before the agent commits. We ruled this out because agents often need to read and test their code *before* committing, and if formatting only happens at commit time, the codebase state is inconsistent during the implementation loop.
- **Dedicated Linter Subagent**: We could have the dispatcher route all file changes to a `linter-agent` as a separate step in the workflow. We ruled this out because it introduces massive latency (another LLM call and network roundtrip) for a task that can be executed instantly via a local script.

## 4. Detailed Implementation
1. **Create `src/harness/templates/boilerplate/hooks/post_tool_use.py`**
   - **Rationale**: Act as the deterministic hook. It will parse standard input for the JSON payload, extract `tool_name` and `tool_input`. If `tool_name` is in `["write_file", "replace", "Edit", "Write"]`, it will extract the file path, switch on the file extension, and run local linting tools via `subprocess`.
2. **Update `src/harness/templates/boilerplate/hooks/hooks.json`**
   - **Rationale**: Register `post_tool_use.py` under the `PostToolUse` event block to ensure it is triggered by Claude Code/Gemini CLI.
3. **Update `src/harness/templates/boilerplate/agents/implementer.md`**
   - **Rationale**: Remove instructions requiring the use of local formatters/linters to save tokens.
4. **Update `src/harness/templates/boilerplate/agents/reviewer.md`**
   - **Rationale**: Explicitly inform the reviewer that deterministic file-formatting and linting are handled automatically on write via hooks, allowing focus on logic and architecture.
5. **Update `.claude` and `.gemini` Live Folders**
   - **Rationale**: Manually mirror all the above changes into the `.claude/` and `.gemini/` directories (the hooks, `hooks.json`, `implementer.md`, `reviewer.md`) so the harness updates are immediately active in the current workspace.
