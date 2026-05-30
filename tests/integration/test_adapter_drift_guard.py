"""Adapter drift guard — throwaway pin for Slice 1.

Pins the runtime behaviour of ``format_hook_response`` and
``get_subagent_text_call`` across **three representations** of each adapter
(claude, gemini) so that Slice 2 (S2-T7) can delete two of them and prove
the surviving copy is behaviour-preserving.

Representations under test
---------------------------
1. Canonical  – ``src/harness/adapters/<P>.py``
   Obtained via ``from harness.adapters import get_adapter; get_adapter("<P>")``.
2. Monolith   – ``src/harness/runtime/platform_adapter.py``
   Obtained via the module-level ``get_adapter("<P>")`` function in that file.
3. Standalone – ``src/harness/runtime/platform_adapter_<P>.py``
   Obtained via the module-level no-arg ``get_adapter()`` in that file.

**RETIRE THIS FILE in S2-T7** alongside ``platform_adapter.py`` and
``platform_adapter_<P>.py``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers to load the two "non-importable" representations at test time
# ---------------------------------------------------------------------------

_RUNTIME_DIR = Path(__file__).parents[2] / "src" / "harness" / "runtime"


def _load_module(name: str, filepath: Path):
    """Load a file as a fresh module by path (avoids package resolution)."""
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Load once at module level so repeated parametrize calls reuse the same objects.
_monolith = _load_module("platform_adapter", _RUNTIME_DIR / "platform_adapter.py")
_standalone_claude = _load_module(
    "platform_adapter_claude", _RUNTIME_DIR / "platform_adapter_claude.py"
)
_standalone_gemini = _load_module(
    "platform_adapter_gemini", _RUNTIME_DIR / "platform_adapter_gemini.py"
)

# ---------------------------------------------------------------------------
# Canonical adapters (via harness package)
# ---------------------------------------------------------------------------

from harness.adapters import get_adapter as _canonical_get_adapter  # noqa: E402

# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

# routing_decision variants that exercise all branches inside format_hook_response
_ROUTING_CASES: list[tuple[str, dict]] = [
    (
        "both_skill_and_agent_ais_true",
        {
            "classification": "SKILL",
            "target_skill": "do-work",
            "target_agent": "@implementer",
            "agent_invokes_skill": True,
        },
    ),
    (
        "both_skill_and_agent_ais_false",
        {
            "classification": "SKILL",
            "target_skill": "do-work",
            "target_agent": "@implementer",
            "agent_invokes_skill": False,
        },
    ),
    (
        "agent_only_generalist",
        {
            "classification": "AGENT",
            "target_agent": "@generalist",
            "target_skill": None,
        },
    ),
    (
        "agent_only_named",
        {
            "classification": "AGENT",
            "target_agent": "@researcher",
            "target_skill": None,
        },
    ),
    (
        "neither",
        {
            "classification": "DIRECT",
            "target_agent": None,
            "target_skill": None,
        },
    ),
]

_SUBAGENT_CALL_CASES: list[tuple[str, str, str | None]] = [
    ("with_skill", "my-agent", "my-skill"),
    ("without_skill", "my-agent", None),
]

# ---------------------------------------------------------------------------
# Parametrize helpers
# ---------------------------------------------------------------------------


def _adapters(platform: str):
    """Return (canonical, monolith, standalone) adapter instances for *platform*."""
    canonical = _canonical_get_adapter(platform)
    monolith = _monolith.get_adapter(platform)
    if platform == "claude":
        standalone = _standalone_claude.get_adapter()
    elif platform == "gemini":
        standalone = _standalone_gemini.get_adapter()
    else:
        raise ValueError(f"Unsupported platform in drift guard: {platform}")
    return canonical, monolith, standalone


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("platform", ["claude", "gemini"])
@pytest.mark.parametrize("routing_label,routing_decision", _ROUTING_CASES)
def test_format_hook_response_identical_across_representations(
    platform: str, routing_label: str, routing_decision: dict
) -> None:
    """All three representations must produce byte-identical output for format_hook_response."""
    canonical, monolith, standalone = _adapters(platform)

    original_prompt = "Please help me with this task."
    context_extension = "Additional context here."
    hook_event_name = "PreToolUse"

    result_canonical = canonical.format_hook_response(
        original_prompt, routing_decision, context_extension, hook_event_name
    )
    result_monolith = monolith.format_hook_response(
        original_prompt, routing_decision, context_extension, hook_event_name
    )
    result_standalone = standalone.format_hook_response(
        original_prompt, routing_decision, context_extension, hook_event_name
    )

    assert result_canonical == result_monolith, (
        f"[{platform}/{routing_label}] DRIFT: canonical != monolith\n"
        f"  canonical:  {result_canonical}\n"
        f"  monolith:   {result_monolith}"
    )
    assert result_canonical == result_standalone, (
        f"[{platform}/{routing_label}] DRIFT: canonical != standalone\n"
        f"  canonical:  {result_canonical}\n"
        f"  standalone: {result_standalone}"
    )


@pytest.mark.parametrize("platform", ["claude", "gemini"])
@pytest.mark.parametrize("case_label,agent_name,skill_name", _SUBAGENT_CALL_CASES)
def test_get_subagent_text_call_identical_across_representations(
    platform: str, case_label: str, agent_name: str, skill_name: str | None
) -> None:
    """All three representations must produce byte-identical output for get_subagent_text_call."""
    canonical, monolith, standalone = _adapters(platform)

    result_canonical = canonical.get_subagent_text_call(agent_name, skill_name)
    result_monolith = monolith.get_subagent_text_call(agent_name, skill_name)
    result_standalone = standalone.get_subagent_text_call(agent_name, skill_name)

    assert result_canonical == result_monolith, (
        f"[{platform}/{case_label}] DRIFT: canonical != monolith\n"
        f"  canonical:  {result_canonical!r}\n"
        f"  monolith:   {result_monolith!r}"
    )
    assert result_canonical == result_standalone, (
        f"[{platform}/{case_label}] DRIFT: canonical != standalone\n"
        f"  canonical:  {result_canonical!r}\n"
        f"  standalone: {result_standalone!r}"
    )
