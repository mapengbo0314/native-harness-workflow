import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


MAX_FAILURE_LINES = 100
MAX_FAILURE_CHARS = 9700


def evaluate_json_path(data, json_path):
    parts = json_path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            if 0 <= idx < len(current):
                current = current[idx]
            else:
                return None
        else:
            return None
    return current


def cap_text(text, max_lines=MAX_FAILURE_LINES, max_chars=MAX_FAILURE_CHARS):
    lines = text.splitlines()
    capped = "\n".join(lines[:max_lines])
    if len(capped) > max_chars:
        capped = capped[:max_chars]
    return capped


def output_to_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return str(value)


def verify_check(check, project_root):
    check_type = check.get("type")

    if check_type in ["file_exists", "does_not_exist", "contains", "not_contains", "regex", "json_path_equals"]:
        path = check.get("path")
        if not path:
            return False, "Missing 'path' for file check"

        full_path = project_root / path

        if check_type == "file_exists":
            return full_path.exists(), f"File '{path}' does not exist"

        if check_type == "does_not_exist":
            return not full_path.exists(), f"File '{path}' exists but should not"

        if not full_path.exists():
            return False, f"File '{path}' does not exist"

        try:
            content = full_path.read_text(encoding="utf-8")
        except Exception as exc:
            return False, f"Could not read '{path}': {exc}"

        if check_type == "contains":
            pattern = check.get("pattern", "")
            return pattern in content, f"Pattern '{pattern}' not found in '{path}'"

        if check_type == "not_contains":
            pattern = check.get("pattern", "")
            return pattern not in content, f"Pattern '{pattern}' found in '{path}'"

        if check_type == "regex":
            pattern = check.get("pattern", "")
            return bool(re.search(pattern, content)), f"Regex '{pattern}' not matched in '{path}'"

        if check_type == "json_path_equals":
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                return False, f"File '{path}' is not valid JSON"

            json_path = check.get("json_path", "")
            expected = check.get("expected_value")
            actual = evaluate_json_path(data, json_path)
            return actual == expected, f"JSON path '{json_path}' in '{path}': expected {expected}, got {actual}"

    elif check_type == "command":
        cmd = check.get("command")
        if not cmd:
            return False, "Missing 'command' field"

        timeout = check.get("timeout_seconds", 60)
        expected_code = check.get("expected_exit_code", 0)
        max_chars = check.get("max_output_chars", 10000)

        try:
            process = subprocess.run(
                cmd,
                shell=True,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            out = (process.stdout + "\n" + process.stderr)[:max_chars]

            if process.returncode != expected_code:
                return False, f"Command '{cmd}' exited with {process.returncode}, expected {expected_code}\nOutput:\n{out}"

            return True, "Command passed"
        except subprocess.TimeoutExpired as exc:
            out = output_to_text(exc.stdout) + "\n" + output_to_text(exc.stderr)
            return False, f"Command '{cmd}' timed out after {timeout} seconds\nOutput:\n{out[:max_chars]}"
        except Exception as exc:
            return False, f"Error running command '{cmd}': {exc}"

    return False, f"Unknown check type: {check_type}"


def resolve_plugin_root():
    if os.environ.get("GEMINI_PLUGIN_ROOT"):
        return Path(os.environ["GEMINI_PLUGIN_ROOT"]).resolve()
    if os.environ.get("CLAUDE_PLUGIN_ROOT"):
        return Path(os.environ["CLAUDE_PLUGIN_ROOT"]).resolve()
    return Path(__file__).resolve().parent.parent


def resolve_contract_path(project_root, explicit_contract=None):
    if explicit_contract:
        return Path(explicit_contract).resolve()

    workspace_contract = project_root / "contracts" / "default_verification_contract.json"
    if workspace_contract.exists():
        return workspace_contract

    plugin_contract = resolve_plugin_root() / "contracts" / "default_verification_contract.json"
    if plugin_contract.exists():
        return plugin_contract

    return workspace_contract


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Verify a workspace against a deterministic contract.")
    parser.add_argument(
        "project_root",
        nargs="?",
        default=os.environ.get("GEMINI_PROJECT_DIR", os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())),
        help="Workspace root to verify.",
    )
    parser.add_argument(
        "--contract",
        help="Explicit contract path. Overrides workspace and plugin defaults.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    project_root = Path(args.project_root).resolve()
    contract_path = resolve_contract_path(project_root, args.contract)

    if not contract_path.exists():
        print(f"No contract found at {contract_path}")
        sys.exit(0)

    try:
        with open(contract_path, "r", encoding="utf-8") as handle:
            contract = json.load(handle)
    except Exception as exc:
        print(f"Error reading contract: {exc}", file=sys.stderr)
        sys.exit(1)

    checks = contract.get("checks", [])
    if not checks:
        print(f"Verification Passed using {contract_path}")
        sys.exit(0)

    errors = []
    for index, check in enumerate(checks):
        passed, message = verify_check(check, project_root)
        if not passed:
            errors.append(f"Check {index + 1} ({check.get('type')}): {message}")

    if errors:
        body = cap_text("\n".join(f"- {err}" for err in errors))
        print(f"Verification Failed: using {contract_path}", file=sys.stderr)
        if body:
            print(body, file=sys.stderr)
        sys.exit(1)

    print(f"Verification Passed using {contract_path}")
    sys.exit(0)


if __name__ == "__main__":
    main()
