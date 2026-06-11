---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
<!-- ported from affaan-m/ECC@c888d2b rules/python/testing.md (curated) -->

# Python Testing

## Framework

Use **pytest** as the testing framework.

## Coverage

```bash
pytest --cov=src --cov-report=term-missing
```

Minimum 80% coverage required. For new modules, aim for 100%.

## Test Organization

Use `pytest.mark` for categorization:

```python
import pytest

@pytest.mark.unit
def test_calculate_total():
    ...

@pytest.mark.integration
def test_database_connection():
    ...
```

## Fixtures

Define fixtures in `conftest.py`; scope them appropriately (`function`/`module`/`session`).
Prefer factory fixtures over shared mutable state.
