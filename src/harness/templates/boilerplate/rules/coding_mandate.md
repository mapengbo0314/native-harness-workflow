# Coding & TDD Mandate

1. **Python Standards**: Composable functions, dataclasses, explicit imports, type hints, and docstrings.
2. **JVM Migration**: Progressive translation to Kotlin (default) or Java. Migrate bounded subsystems. Generate design notes. Align test fixtures.
3. **TDD Lifecycle**: You MUST follow strict Test-Driven Development.
   - **RED**: Write a failing test first. Verify the failure in the logs.
   - **GREEN**: Write the minimal code to pass the test.
   - **REFACTOR**: Improve the code while keeping tests passing.
4. **Documentation**: State inputs, outputs, and failure modes. Reference source evidence.
