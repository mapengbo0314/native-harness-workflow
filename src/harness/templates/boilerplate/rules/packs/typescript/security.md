---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
---
<!-- ported from affaan-m/ECC@c888d2b rules/typescript/security.md (curated) -->

# TypeScript/JavaScript Security

## Secret Management

```typescript
// NEVER: hardcoded secrets
const apiKey = "sk-proj-xxxxx"

// ALWAYS: environment variables
const apiKey = process.env.API_KEY
if (!apiKey) {
  throw new Error('API_KEY not configured')
}
```

## Input Validation

- Use **Zod** (or equivalent schema library) to validate all external input at the boundary.
- Never trust data from API responses, user input, or file content without validation.
