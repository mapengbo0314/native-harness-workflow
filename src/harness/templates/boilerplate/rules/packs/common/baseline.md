# Baseline Review Rules

These rules apply to all code, regardless of language or framework.

## Code Quality

- Prefer clarity over cleverness. Code should be readable without needing inline comments.
- Avoid deep nesting (more than 3 levels); refactor into well-named helper functions.
- Functions should do one thing and name that thing accurately.

## Safety

- Never commit secrets, credentials, or API keys to source control.
- Validate all external inputs at the boundary; never trust data from outside the process.
- Handle errors explicitly; do not silently swallow exceptions.

## Consistency

- Follow the project's established naming conventions.
- Keep related logic together; split unrelated logic into separate modules.

<!-- placeholder: content authored in Task 1c from ECC@c888d2b -->
