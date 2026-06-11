# Testing Requirements

<!-- ported from affaan-m/ECC@c888d2b rules/common/testing.md (curated) -->

## Minimum Test Coverage: 80%

Required test types:
1. **Unit Tests** — individual functions, utilities, pure logic.
2. **Integration Tests** — API endpoints, database operations, service boundaries.
3. **E2E Tests** — critical user flows (framework per language).

## Test-Driven Development

Mandatory workflow:
1. Write test first (RED — test must fail).
2. Write minimal implementation (GREEN — test must pass).
3. Refactor (IMPROVE — keep tests green).
4. Verify coverage ≥80%.

## Test Structure (AAA Pattern)

```
Arrange — set up state and inputs
Act     — call the unit under test
Assert  — verify the outcome
```

Use descriptive test names that explain the behavior under test:
- `returns_empty_array_when_no_markets_match_query`
- `raises_error_when_api_key_is_missing`

## Troubleshooting Failures

1. Check test isolation — tests must not share mutable state.
2. Verify mocks are correct and reset between tests.
3. Fix the implementation, not the tests (unless the test is wrong).