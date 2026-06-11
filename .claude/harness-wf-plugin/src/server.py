"""harness.domain.server — MCP server exposing domain_ops(topic).

Exposes a single pull tool, ``domain_ops``, that returns the requested slice
of the repo's ``domain.json`` manifest.  The tool is registered with FastMCP
and can be run as a stdio MCP server via ``main()``.

Environment:
    DOMAIN_JSON_PATH — if set, must point directly to the ``domain.json``
        file (overrides ancestor-walk discovery).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from model import OpsManifest, TOPICS

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_MANIFEST_FILENAME = "domain.json"


def find_manifest_path(start: Optional[Path] = None) -> Optional[Path]:
    """Return the path to ``domain.json``, or ``None`` if not found.

    Resolution order:
    1. ``DOMAIN_JSON_PATH`` env var — returned as-is if the file exists, else ``None``.
    2. Walk *start* (defaults to cwd) and each ancestor looking for ``domain.json``.
    """
    env_path = os.environ.get("DOMAIN_JSON_PATH")
    if env_path:
        p = Path(env_path)
        return p if p.exists() else None

    search_start = Path(start).resolve() if start is not None else Path.cwd()
    # Walk this dir and all parents
    for directory in [search_start, *search_start.parents]:
        candidate = directory / _MANIFEST_FILENAME
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Manifest loader
# ---------------------------------------------------------------------------

def load_manifest(path: Optional[Path] = None) -> OpsManifest:
    """Load and return an OpsManifest.

    Uses *path* if provided; falls back to ``find_manifest_path()``.
    Returns an empty ``OpsManifest()`` if no file is found or *path* does
    not exist.
    """
    p = path if path is not None else find_manifest_path()
    if p is None or not Path(p).exists():
        return OpsManifest()
    return OpsManifest.load(p)


# ---------------------------------------------------------------------------
# Pure tool logic (unit-tested independently of MCP wiring)
# ---------------------------------------------------------------------------

def tool_domain_ops(topic: str = "all", *, manifest: OpsManifest) -> dict:
    """Return the manifest slice for *topic*.

    This is the pure, side-effect-free implementation used both by the MCP
    tool wrapper and by unit tests.
    """
    return manifest.topic(topic)


# ---------------------------------------------------------------------------
# FastMCP wiring
# ---------------------------------------------------------------------------

mcp = FastMCP("domain")


@mcp.tool()
def domain_ops(topic: str = "all") -> dict:
    """Pull operational and business context from this repo's domain.json.

    Call this tool before build, test, or deploy tasks to get accurate
    repo-specific commands, environment details, and business priorities.

    Available topics:
      - "stack"        — languages and frameworks
      - "environments" — env URLs / config
      - "test"         — how to run tests
      - "deploy"       — deploy commands and targets
      - "infra"        — infrastructure provider / services
      - "references"   — runbooks and reference links
      - "business"     — direction, priorities, constraints, non-goals
      - "all"          — all of the above (default)

    Pass a specific topic for a focused slice; omit or pass "all" for everything.
    """
    return tool_domain_ops(topic, manifest=load_manifest())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:  # pragma: no cover
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()
