---
paths:
  - "**/*.go"
  - "**/go.mod"
  - "**/go.sum"
---
<!-- ported from affaan-m/ECC@c888d2b rules/golang/testing.md (curated) -->

# Go Testing

## Framework

Use the standard `go test` toolchain with **table-driven tests**.

## Race Detection

Always run with the `-race` flag in CI:

```bash
go test -race ./...
```

## Coverage

```bash
go test -cover ./...
```

Minimum 80% coverage. Use `go test -coverprofile=coverage.out ./...` for detailed reports.

## Table-Driven Test Pattern

```go
func TestAdd(t *testing.T) {
    cases := []struct {
        name     string
        a, b     int
        expected int
    }{
        {"positive", 1, 2, 3},
        {"zero", 0, 0, 0},
    }
    for _, tc := range cases {
        t.Run(tc.name, func(t *testing.T) {
            got := Add(tc.a, tc.b)
            if got != tc.expected {
                t.Errorf("Add(%d,%d) = %d, want %d", tc.a, tc.b, got, tc.expected)
            }
        })
    }
}
```
