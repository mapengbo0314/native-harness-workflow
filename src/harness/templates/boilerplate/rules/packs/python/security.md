---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
<!-- ported from affaan-m/ECC@c888d2b rules/python/security.md (curated) -->

# Python Security

## Secret Management

```python
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ["OPENAI_API_KEY"]  # Raises KeyError if missing — fail fast
```

Never use `os.getenv("KEY", "default-secret")` for secrets; missing secrets must be fatal.

## Security Scanning

Run **bandit** as part of CI:

```bash
bandit -r src/
```
