"""harness.domain.model — Typed model for domain.json (stdlib-only).

The OpsManifest dataclass parses and exposes the seven operational + business
topic sections that make up a repo's domain.json file.  All I/O is plain
JSON; no third-party dependencies are required.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

TOPICS: tuple[str, ...] = (
    "stack",
    "environments",
    "test",
    "deploy",
    "infra",
    "references",
    "business",
)

def _clean(d: object) -> dict:
    """Return a copy of *d* with blank values removed.

    Dropped values: ``""``, ``None``, ``[]``, ``{}``; whitespace-only strings.
    Non-empty lists are kept intact.
    """
    if not isinstance(d, dict):
        return {}
    out: dict = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, str):
            if v.strip() == "":
                continue
        elif isinstance(v, (list, dict)):
            if len(v) == 0:
                continue
        out[k] = v
    return out


@dataclass
class OpsManifest:
    """Parsed view of a ``domain.json`` manifest."""

    schema_version: int = 1
    stack: tuple[str, ...] = ()
    environments: dict = field(default_factory=dict)
    test: dict = field(default_factory=dict)
    deploy: dict = field(default_factory=dict)
    infra: dict = field(default_factory=dict)
    references: dict = field(default_factory=dict)
    business: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict) -> "OpsManifest":
        """Build an OpsManifest from a plain dict (e.g. parsed JSON)."""
        schema_version = int(data.get("schema_version", 1))
        raw_stack = data.get("stack") or []
        stack = tuple(s for s in raw_stack if isinstance(s, str) and s.strip())
        return cls(
            schema_version=schema_version,
            stack=stack,
            environments=_clean(data.get("environments", {})),
            test=_clean(data.get("test", {})),
            deploy=_clean(data.get("deploy", {})),
            infra=_clean(data.get("infra", {})),
            references=_clean(data.get("references", {})),
            business=_clean(data.get("business", {})),
        )

    @classmethod
    def from_json(cls, text: str) -> "OpsManifest":
        """Parse JSON text and return an OpsManifest.

        An empty or whitespace-only *text* is treated as an empty manifest.
        """
        if not text or not text.strip():
            return cls.from_dict({})
        return cls.from_dict(json.loads(text))

    @classmethod
    def load(cls, path) -> "OpsManifest":
        """Read a JSON file and return an OpsManifest."""
        text = Path(path).read_text(encoding="utf-8")
        return cls.from_json(text)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def as_dict(self) -> dict:
        """Return all seven topics as a plain dict (stack is a list)."""
        return {
            "stack": list(self.stack),
            "environments": self.environments,
            "test": self.test,
            "deploy": self.deploy,
            "infra": self.infra,
            "references": self.references,
            "business": self.business,
        }

    def topic(self, name: Optional[str]) -> dict:
        """Return the slice for *name* (case-insensitive).

        - ``"all"``, ``""``, or ``None`` → full ``as_dict()``.
        - ``"stack"`` → ``{"stack": [...]}``.
        - Any other valid topic → ``{name: <section dict>}``.
        - Unknown name → ``{}``.
        """
        name = (name or "all").strip().lower()
        if name == "all":
            return self.as_dict()
        if name == "stack":
            return {"stack": list(self.stack)}
        if name in TOPICS:
            return {name: getattr(self, name)}
        return {}
