---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
<!-- ported from affaan-m/ECC@c888d2b rules/python/coding-style.md (curated) -->

# Python Coding Style

## Standards

- Follow **PEP 8** conventions.
- Use **type annotations** on all function signatures.

## Immutability

Prefer immutable data structures:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class User:
    name: str
    email: str

from typing import NamedTuple

class Point(NamedTuple):
    x: float
    y: float
```

## Formatting

- **black** for code formatting.
- **isort** for import sorting.
- **ruff** for linting.

## Patterns

```python
from typing import Protocol

class Repository(Protocol):
    def find_by_id(self, id: str) -> dict | None: ...
    def save(self, entity: dict) -> dict: ...
```

Use dataclasses as DTOs:

```python
from dataclasses import dataclass

@dataclass
class CreateUserRequest:
    name: str
    email: str
    age: int | None = None
```

Use context managers for resource management; generators for lazy/memory-efficient iteration.
