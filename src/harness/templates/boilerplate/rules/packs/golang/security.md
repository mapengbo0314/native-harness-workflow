---
paths:
  - "**/*.go"
  - "**/go.mod"
  - "**/go.sum"
---
<!-- ported from affaan-m/ECC@c888d2b rules/golang/security.md (curated) -->

# Go Security

## Secret Management

```go
apiKey := os.Getenv("OPENAI_API_KEY")
if apiKey == "" {
    log.Fatal("OPENAI_API_KEY not configured")
}
```

## Security Scanning

Run **gosec** as part of CI:

```bash
gosec ./...
```

## Context & Timeouts

Always use `context.Context` for timeout and cancellation control:

```go
ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
defer cancel()
```

Never pass `context.Background()` from a goroutine into a long-lived operation without a timeout.
