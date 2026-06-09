#!/usr/bin/env python3
"""PostToolUse hook: format files after Edit/Write — opt-in only.

Formatting runs ONLY when the project contains .claude/.harness-format-enabled.
Bootstrap projects get this file automatically via mint_workspace.
Retrofit projects must add it manually after fixing all pre-existing formatting
so the formatter never silently lands in a PR diff.
"""
import json
import sys
import shutil
import subprocess
from pathlib import Path

# Import project-root resolver from the shared hook library.
sys.path.insert(0, str(Path(__file__).parent))
from hook_common import resolve_project_root

SENTINEL = ".claude/.harness-format-enabled"

PRETTIER_CONFIGS = [
    ".prettierrc", ".prettierrc.json", ".prettierrc.yaml", ".prettierrc.yml",
    ".prettierrc.js", ".prettierrc.cjs", ".prettierrc.mjs",
    "prettier.config.js", "prettier.config.cjs", "prettier.config.mjs",
]

RUFF_CONFIGS = ["ruff.toml", ".ruff.toml"]


def _find_upward(start: Path, names: list) -> bool:
    """Return True if any of `names` exist in `start` or any ancestor."""
    for directory in [start, *start.parents]:
        if any((directory / name).exists() for name in names):
            return True
    return False


def get_formatter_commands(file_path: Path, project_root: Path) -> list[list[str]]:
    """Return formatter commands for `file_path`, respecting project config."""
    ext = file_path.suffix.lower()

    if ext == ".py":
        if not shutil.which("ruff"):
            return []
        # Only run ruff when the project has a ruff config.
        has_ruff_cfg = _find_upward(file_path.parent, RUFF_CONFIGS) or \
            _find_upward(file_path.parent, ["pyproject.toml"])
        if not has_ruff_cfg:
            return []
        return [
            ["ruff", "format", str(file_path)],
            ["ruff", "check", "--fix", str(file_path)],
        ]

    if ext in {".js", ".jsx", ".ts", ".tsx", ".json", ".md"}:
        if not shutil.which("prettier") and not shutil.which("npx"):
            return []
        # Only run prettier when the project has a prettier config.
        if not _find_upward(file_path.parent, PRETTIER_CONFIGS):
            return []
        cmd = ["prettier", "--write", str(file_path)] if shutil.which("prettier") \
            else ["npx", "--no-install", "prettier", "--write", str(file_path)]
        return [cmd]

    return []


def _noop(is_gemini: bool) -> None:
    if is_gemini:
        print(json.dumps({}))
    sys.exit(0)


def main():
    try:
        input_str = sys.stdin.read()
        if not input_str.strip():
            print(json.dumps({}))
            sys.exit(0)

        input_data = json.loads(input_str)
        is_gemini = "hook_event_name" in input_data

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Only format after modifying tools.
        if tool_name not in {"Write", "Edit", "Edit", "Write", "MultiEdit"}:
            _noop(is_gemini)

        file_path_str = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("file")
        if not file_path_str:
            _noop(is_gemini)

        file_path = Path(file_path_str)
        if not file_path.exists():
            _noop(is_gemini)

        project_root = resolve_project_root(input_data)

        # Formatting is opt-in. Retrofit projects must add the sentinel after
        # fixing pre-existing formatting so the hook never pollutes PR diffs.
        if not (project_root / SENTINEL).exists():
            _noop(is_gemini)

        commands = get_formatter_commands(file_path, project_root)
        for cmd in commands:
            try:
                subprocess.run(
                    cmd,
                    cwd=str(project_root),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception as e:
                print(f"Linter warning: failed to run {' '.join(cmd)}: {e}", file=sys.stderr)

        if is_gemini:
            print(json.dumps({}))
            sys.exit(0)

    except Exception as e:
        print(f"Post-tool-use hook error: {e}", file=sys.stderr)
        if "input_str" in locals() and "hook_event_name" in input_str:
            print(json.dumps({}))
        sys.exit(0)


if __name__ == "__main__":
    main()