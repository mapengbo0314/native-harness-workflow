#!/usr/bin/env python3
"""
Compute a short fingerprint for the currently installed harness configuration.

The ID is derived from:
  - skill content hashes in skills-lock.json
  - agent roster + version in .claude/agent.json
  - platform and model (from env or CLI args)

Identical configs across machines produce the same ID, so Langfuse run_name
comparisons are meaningful across developers.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def compute_config_id(
    skills_lock_path: Path,
    agent_json_path: Path,
    platform: str,
    model: str,
) -> str:
    parts = []

    if skills_lock_path.exists():
        with open(skills_lock_path) as f:
            skills_lock = json.load(f)
        for name in sorted(skills_lock.get("skills", {})):
            h = skills_lock["skills"][name].get("computedHash", "")
            parts.append(f"skill:{name}:{h}")

    if agent_json_path.exists():
        with open(agent_json_path) as f:
            agent = json.load(f)
        parts.append(f"agent_version:{agent.get('version', '0')}")
        for skill in sorted(agent.get("skills", [])):
            parts.append(f"agent_skill:{skill}")
        for rel in sorted(agent.get("related_agents", [])):
            parts.append(f"agent_rel:{rel}")

    parts.append(f"platform:{platform}")
    parts.append(f"model:{model}")

    raw = "\n".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:8]


def get_config_id(project_root: Path = None, platform: str = None, model: str = None) -> str:
    root = (project_root or Path(".")).resolve()
    platform = platform or os.environ.get("HARNESS_PLATFORM", "claude")
    model = model or os.environ.get("HARNESS_MODEL", "unknown")
    return compute_config_id(
        root / "skills-lock.json",
        root / ".claude" / "agent.json",
        platform,
        model,
    )


def main():
    parser = argparse.ArgumentParser(description="Print the current harness config ID.")
    parser.add_argument("--project-root", default=".", help="Project root (default: cwd)")
    parser.add_argument("--platform", default=None, help="Platform override (e.g. claude, gemini)")
    parser.add_argument("--model", default=None, help="Model override (e.g. claude-sonnet-4-6)")
    args = parser.parse_args()

    config_id = get_config_id(Path(args.project_root), args.platform, args.model)
    print(config_id)


if __name__ == "__main__":
    main()
