# Baseline Coding Rules

<!-- ported from affaan-m/ECC@c888d2b rules/common/coding-style.md (curated) -->
<!-- ported from affaan-m/ECC@c888d2b rules/common/code-review.md (curated) -->

## Immutability

ALWAYS create new objects, NEVER mutate existing ones.

Rationale: Immutable data prevents hidden side effects, makes debugging easier, and enables safe concurrency.

## Core Principles

- **KISS**: Prefer the simplest solution that actually works; optimize for clarity over cleverness.
- **DRY**: Extract repeated logic into shared functions; avoid copy-paste drift.
- **YAGNI**: Do not build abstractions before they are needed.

## File & Function Size

- Functions: ≤50 lines; files: ≤800 lines.
- Prefer many small, cohesive files over a few large ones.

## Error Handling

- Handle errors explicitly at every level.
- Never silently swallow errors.
- Validate all external inputs at system boundaries; never trust data from outside the process.

## Naming

- Variables/functions: `camelCase` (or language-idiomatic). Booleans: `is`/`has`/`should`/`can` prefix.
- Constants: `UPPER_SNAKE_CASE`. Types/classes: `PascalCase`.
- Avoid magic numbers; use named constants.

## Code Smells to Avoid

- Deep nesting (>4 levels) — use early returns.
- Large functions (>50 lines) — split into focused pieces.
- Hardcoded values — use constants or config.

## Code Review Checklist

Before marking work complete:
- [ ] Code is readable and well-named
- [ ] Functions are small (<50 lines); files focused (<800 lines)
- [ ] No deep nesting (>4 levels)
- [ ] Errors handled explicitly; no silent swallowing
- [ ] No hardcoded secrets or credentials
- [ ] Tests exist for new functionality (coverage ≥80%)

## Review Severity Levels

| Level | Meaning | Action |
|-------|---------|--------|
| CRITICAL | Security vulnerability or data loss risk | **BLOCK** before merge |
| HIGH | Bug or significant quality issue | **WARN** — should fix |
| MEDIUM | Maintainability concern | **INFO** — consider fixing |
| LOW | Style / minor suggestion | **NOTE** — optional |