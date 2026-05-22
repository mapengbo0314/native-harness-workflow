# Coding & TDD Mandate

1. **Python Standards**: Composable functions, dataclasses, explicit imports, type hints, and docstrings.
2. **Graph-First Strategy**: ALWAYS prioritize CodeGraph MCP tools (`codegraph_search`, `codegraph_context`, `codegraph_callers`) over broad filesystem searches or reading full files. Only use `read_file` or `grep_search` when Graph tools are insufficient.
3. **JVM Migration**: Progressive translation to Kotlin (default) or Java. Migrate bounded subsystems. Generate design notes. Align test fixtures.
4. **TDD Lifecycle**: You MUST follow strict Test-Driven Development.
   - **RED**: Write a failing test first. Verify the failure in the logs.
   - **GREEN**: Write the minimal code to pass the test.
   - **REFACTOR**: Improve the code while keeping tests passing.
5. **Documentation**: State inputs, outputs, and failure modes. Reference source evidence.
