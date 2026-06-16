---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
---
<!-- ported from affaan-m/ECC@c888d2b rules/typescript/coding-style.md (curated) -->

# TypeScript/JavaScript Coding Style

## Types and Interfaces

- Add parameter and return types to all exported functions and public class methods.
- Use `interface` for object shapes; `type` for unions, intersections, and utility types.
- Prefer string literal unions over `enum` unless interoperability requires it.
- Avoid `any`; use `unknown` for external/untrusted input and narrow it safely.

```typescript
// WRONG
function getErrorMessage(error: any) { return error.message }

// CORRECT
function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'Unexpected error'
}
```

## Immutability

Use spread for immutable updates:

```typescript
// WRONG: mutation
function updateUser(user: User, name: string): User {
  user.name = name
  return user
}

// CORRECT: immutability
function updateUser(user: Readonly<User>, name: string): User {
  return { ...user, name }
}
```

## Input Validation

Use **Zod** for schema-based validation; infer types from the schema:

```typescript
import { z } from 'zod'

const userSchema = z.object({
  email: z.string().email(),
  age: z.number().int().min(0).max(150)
})

type UserInput = z.infer<typeof userSchema>
const validated: UserInput = userSchema.parse(input)
```

## Error Handling

Use `async/await` + `try/catch`; narrow `unknown` errors safely before accessing properties.

## Console.log

No `console.log` in production code; use a structured logging library instead.