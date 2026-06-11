---
paths: ["**/*.ts", "**/*.tsx"]
---

# TypeScript-Specific Review Rules

These rules apply to TypeScript and TSX source files.

## Types

- Avoid `any`; use `unknown` with a type guard if the type is truly unknown.
- Prefer explicit return type annotations on exported functions.
- Use `interface` for object shapes that may be extended; use `type` for unions and aliases.

## Patterns

- Use `const` by default; only use `let` when reassignment is necessary.
- Prefer optional chaining (`?.`) and nullish coalescing (`??`) over manual null checks.
- Avoid implicit coercion; use strict equality (`===`) throughout.

## React / TSX (when applicable)

- Keep components small and focused; extract logic into custom hooks.
- Type all props explicitly with interfaces; avoid `React.FC` — prefer plain function declarations.

<!-- placeholder: content authored in Task 1c from ECC@c888d2b -->
