# full_harness config

Uses the harness plugin snapshot from `tests/fixtures/snapshots/claude_plugin/`.

The runner mints a fresh plugin into the target project using:
    harness-wf init --project-path <target>

This ensures the full_harness config always reflects the current harness version.
