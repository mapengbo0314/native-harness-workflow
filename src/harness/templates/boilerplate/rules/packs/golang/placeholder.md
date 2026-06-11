---
paths: ["**/*.go"]
---

# Go-Specific Review Rules

These rules apply to Go source files.

## Error Handling

- Always check and handle errors explicitly; never use `_` to discard an error from a fallible call.
- Wrap errors with context using `fmt.Errorf("doing X: %w", err)` so call sites can inspect the chain.
- Return early on errors; avoid deeply nested success paths.

## Style

- Follow the conventions enforced by `gofmt` and `golangci-lint`.
- Keep package names short, lowercase, and without underscores.
- Unexported identifiers should still have clear, descriptive names.

## Concurrency

- Protect shared state with mutexes or channels; never communicate by sharing memory.
- Document goroutine lifetimes; make it clear who is responsible for cancellation.

<!-- placeholder: content authored in Task 1c from ECC@c888d2b -->
