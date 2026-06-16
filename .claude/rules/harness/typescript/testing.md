---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
---
<!-- ported from affaan-m/ECC@c888d2b rules/typescript/testing.md (curated) -->

# TypeScript/JavaScript Testing

## Unit & Integration

- Use **Vitest** (preferred) or **Jest** for unit and integration tests.
- Co-locate test files as `*.test.ts` or `*.spec.ts` next to the source.
- Minimum 80% coverage.

## E2E Testing

Use **Playwright** for critical user flows:

```bash
npx playwright test
```

## Test Naming

Describe the behavior, not the implementation:

```typescript
test('returns empty array when no markets match query', () => {})
test('throws error when API key is missing', () => {})
```