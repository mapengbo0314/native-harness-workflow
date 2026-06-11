---
paths: ["**/*.py"]
---

# Python-Specific Review Rules

These rules apply to Python source files.

## Style

- Follow PEP 8 conventions; use tools like `ruff` or `black` for formatting.
- Use type annotations on all public function signatures.
- Prefer `pathlib.Path` over `os.path` string manipulation.

## Patterns

- Use context managers (`with`) for resource management (files, locks, connections).
- Prefer list/dict/set comprehensions over imperative loops where the intent is clear.
- Avoid mutable default arguments; use `None` sentinel and assign defaults in the body.

## Testing

- Each public function should have at least one unit test covering the happy path.
- Use `pytest` fixtures for setup/teardown; avoid global test state.

<!-- placeholder: content authored in Task 1c from ECC@c888d2b -->
