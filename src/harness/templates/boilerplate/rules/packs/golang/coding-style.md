---
paths:
  - "**/*.go"
  - "**/go.mod"
  - "**/go.sum"
---
<!-- ported from affaan-m/ECC@c888d2b rules/golang/coding-style.md (curated) -->

# Go Coding Style

## Formatting

- **gofmt** and **goimports** are mandatory — no style debates.

## Design Principles

- Accept interfaces, return structs.
- Keep interfaces small (1–3 methods); define them where they are used, not where implemented.

## Error Handling

Always wrap errors with context:

```go
if err != nil {
    return fmt.Errorf("failed to create user: %w", err)
}
```

Never ignore errors; use `_` only when documented reason exists.

## Patterns

**Functional Options:**

```go
type Option func(*Server)

func WithPort(port int) Option {
    return func(s *Server) { s.port = port }
}

func NewServer(opts ...Option) *Server {
    s := &Server{port: 8080}
    for _, opt := range opts { opt(s) }
    return s
}
```

**Dependency Injection via constructors:**

```go
func NewUserService(repo UserRepository, logger Logger) *UserService {
    return &UserService{repo: repo, logger: logger}
}
```
