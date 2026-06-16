"""
profile.py — Typed accessor for platform profiles.

IMPORTANT: stdlib-only — ZERO harness.* imports.
This file is designed to be copied standalone (next to platform_profiles.json)
into the minted plugin (S2-T6), so it must work without the harness package.

Usage:
    from profile import load_profile, PlatformProfile

    p = load_profile("claude")
    p.skill_invocation("my-skill")        # 'Skill("my-skill")'
    p.subagent_invocation("coder", "…")   # 'Task(subagent_type="coder", description="…")'
    p.subagent_text_call("coder")         # 'Task(subagent_type="coder")'
    p.subagent_text_call("coder", skill="foo")  # with-skill variant
"""

from __future__ import annotations

import functools
import json
import dataclasses
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------

class ProfileError(ValueError):
    """Raised when a platform is unknown or a required key is missing."""


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

REQUIRED_KEYS: tuple[str, ...] = (
    "platform_name",
    "config_dir",
    "plugin_env_var",
    "tool_mappings",
    "event_mappings",
    "skill_invocation",
    "subagent_invocation",
    "subagent_text_call",
    "manifest_format",
    "rules_pointer_files",
    "supports_plugin",
    "plugin_dir_name",
    "generalist_remap",
    "hook_agent_only_cta",
)

REQUIRED_SUBAGENT_TEXT_CALL_KEYS: tuple[str, ...] = ("without_skill", "with_skill")


@dataclasses.dataclass(frozen=True)
class PlatformProfile:
    """Frozen, typed representation of one platform entry in platform_profiles.json."""

    platform_name: str
    config_dir: str
    plugin_env_var: str
    tool_mappings: Dict[str, str]
    event_mappings: Dict[str, str]
    # Raw template strings (used by accessor methods below)
    skill_invocation_tpl: str
    subagent_invocation_tpl: str
    subagent_text_call_without_skill: str
    subagent_text_call_with_skill: str
    manifest_format: str
    rules_pointer_files: List[str]
    supports_plugin: bool
    plugin_dir_name: Optional[str]
    # Hook formatting behaviour flags
    generalist_remap: bool
    hook_agent_only_cta: str

    # ------------------------------------------------------------------
    # Convenience accessors (template formatters)
    # ------------------------------------------------------------------

    def skill_invocation(self, skill_name: str) -> str:
        """Format the skill-invocation template for a given skill name."""
        return self.skill_invocation_tpl.replace("{skill}", skill_name)

    def subagent_invocation(self, agent: str, description: str) -> str:
        """Format the subagent-invocation template."""
        return (
            self.subagent_invocation_tpl
            .replace("{agent}", agent)
            .replace("{description}", description)
        )

    def domain_root_rel(self) -> str:
        """The deployed root (relative to the project root) that holds the
        domain MCP's ``domain/`` and ``src/`` payload.

        - plugin platforms (claude): ``<config_dir>/<plugin_dir_name>``
          (e.g. ``.claude/harness-wf-plugin``).
        - embedded platforms (gemini/cursor/codex/generic): ``<config_dir>``
          (e.g. ``.gemini``).

        DOMAIN_JSON_PATH = ``<root>/domain/domain.json`` and
        PYTHONPATH = ``<root>/src`` are derived from this.
        """
        if self.supports_plugin and self.plugin_dir_name:
            return f"{self.config_dir}/{self.plugin_dir_name}"
        return self.config_dir

    def subagent_text_call(self, agent: str, skill: Optional[str] = None) -> str:
        """
        Format the subagent text-call template.

        If *skill* is provided the 'with_skill' variant is used;
        otherwise the 'without_skill' variant.
        """
        if skill is not None:
            return (
                self.subagent_text_call_with_skill
                .replace("{agent}", agent)
                .replace("{skill}", skill)
            )
        return self.subagent_text_call_without_skill.replace("{agent}", agent)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_DEFAULT_PROFILES_PATH = Path(__file__).parent / "platform_profiles.json"


def load_profile(
    platform: str,
    *,
    _profiles_path: Optional[Path] = None,
) -> PlatformProfile:
    """
    Load and validate the profile for *platform* from platform_profiles.json.

    Cached per (platform, path): adapters call this from nearly every getter,
    so the JSON is read and validated once per process, not per call.

    Args:
        platform: Platform key (e.g. "claude", "gemini", "codex", "cursor", "generic").
        _profiles_path: Override the JSON path (for testing with synthetic data).

    Returns:
        A frozen :class:`PlatformProfile` instance.

    Raises:
        ProfileError: If *platform* is not found in the JSON.
        ProfileError: If a required key is absent from the platform's entry.
    """
    profiles_path = _profiles_path if _profiles_path is not None else _DEFAULT_PROFILES_PATH
    return _load_profile_cached(platform, str(profiles_path))


@functools.lru_cache(maxsize=None)
def _load_profile_cached(platform: str, profiles_path: str) -> PlatformProfile:
    with open(profiles_path, encoding="utf-8") as fh:
        data: dict = json.load(fh)

    if not platform or platform not in data:
        known = sorted(data.keys())
        raise ProfileError(
            f"Unknown platform {platform!r}. Known platforms: {known}"
        )

    raw: dict = data[platform]

    # Validate top-level required keys
    missing_top = [k for k in REQUIRED_KEYS if k not in raw]
    if missing_top:
        raise ProfileError(
            f"Platform {platform!r} is missing required keys: {missing_top}"
        )

    # Validate subagent_text_call sub-keys
    stc = raw["subagent_text_call"]
    if not isinstance(stc, dict):
        raise ProfileError(
            f"Platform {platform!r}: 'subagent_text_call' must be an object, got {type(stc).__name__}"
        )
    missing_stc = [k for k in REQUIRED_SUBAGENT_TEXT_CALL_KEYS if k not in stc]
    if missing_stc:
        raise ProfileError(
            f"Platform {platform!r}: 'subagent_text_call' is missing keys: {missing_stc}"
        )

    return PlatformProfile(
        platform_name=raw["platform_name"],
        config_dir=raw["config_dir"],
        plugin_env_var=raw["plugin_env_var"],
        tool_mappings=dict(raw["tool_mappings"]),
        event_mappings=dict(raw["event_mappings"]),
        skill_invocation_tpl=raw["skill_invocation"],
        subagent_invocation_tpl=raw["subagent_invocation"],
        subagent_text_call_without_skill=stc["without_skill"],
        subagent_text_call_with_skill=stc["with_skill"],
        manifest_format=raw["manifest_format"],
        rules_pointer_files=list(raw["rules_pointer_files"]),
        supports_plugin=bool(raw["supports_plugin"]),
        plugin_dir_name=raw["plugin_dir_name"],
        generalist_remap=bool(raw["generalist_remap"]),
        hook_agent_only_cta=raw["hook_agent_only_cta"],
    )
