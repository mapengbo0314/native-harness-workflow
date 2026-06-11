# Security Guidelines

<!-- ported from affaan-m/ECC@c888d2b rules/common/security.md (curated) -->

## Mandatory Security Checks

Before ANY commit:
- [ ] No hardcoded secrets (API keys, passwords, tokens)
- [ ] All user inputs validated and sanitized
- [ ] SQL injection prevention (parameterized queries only)
- [ ] XSS prevention (sanitized HTML output)
- [ ] CSRF protection enabled on mutating endpoints
- [ ] Authentication and authorization verified on every sensitive path
- [ ] Rate limiting on all public-facing endpoints
- [ ] Error messages do not leak sensitive data or stack traces

## Secret Management

- NEVER hardcode secrets in source code.
- ALWAYS use environment variables or a dedicated secret manager.
- Validate that required secrets are present at startup (fail fast with a clear error).
- Rotate any secrets that may have been exposed immediately.

## Security Response Protocol

If a security issue is found:
1. STOP — do not continue adding features.
2. Fix CRITICAL issues before any other work.
3. Rotate any exposed secrets.
4. Review the entire codebase for similar patterns.
