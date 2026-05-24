import json
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).parent.parent.parent
    / "src"
    / "harness"
    / "templates"
    / "boilerplate"
    / "scripts"
    / "verify_contract.py"
)


def write_contract(path, checks):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "checks": checks}))


def run_verifier(project_root, *args, env=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(project_root), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_verify_contract_success(tmp_path):
    write_contract(
        tmp_path / "contracts" / "default_verification_contract.json",
        [
            {"type": "file_exists", "path": "test_file.txt"},
            {"type": "command", "command": "echo 'hello'", "expected_exit_code": 0},
        ],
    )
    (tmp_path / "test_file.txt").write_text("hello world")

    process = run_verifier(tmp_path)

    assert process.returncode == 0, process.stderr
    assert "Verification Passed" in process.stdout


def test_verify_contract_failure(tmp_path):
    write_contract(
        tmp_path / "contracts" / "default_verification_contract.json",
        [{"type": "file_exists", "path": "missing_file.txt"}],
    )

    process = run_verifier(tmp_path)

    assert process.returncode == 1
    assert "Verification Failed:" in process.stderr
    assert "missing_file.txt" in process.stderr


def test_file_assertion_types(tmp_path):
    (tmp_path / "test.txt").write_text("secret_code\nversion = 12\n")
    (tmp_path / "data.json").write_text(json.dumps({"tool": {"enabled": True}}))
    write_contract(
        tmp_path / "contracts" / "default_verification_contract.json",
        [
            {"type": "file_exists", "path": "test.txt"},
            {"type": "does_not_exist", "path": "missing.txt"},
            {"type": "contains", "path": "test.txt", "pattern": "secret_code"},
            {"type": "not_contains", "path": "test.txt", "pattern": "do_not_ship"},
            {"type": "regex", "path": "test.txt", "pattern": r"version = \d+"},
            {
                "type": "json_path_equals",
                "path": "data.json",
                "json_path": "tool.enabled",
                "expected_value": True,
            },
        ],
    )

    process = run_verifier(tmp_path)

    assert process.returncode == 0, process.stderr


def test_command_assertion_failure_is_nonzero(tmp_path):
    write_contract(
        tmp_path / "contracts" / "default_verification_contract.json",
        [
            {
                "type": "command",
                "command": f"{sys.executable} -c \"import sys; print('bad'); sys.exit(3)\"",
                "expected_exit_code": 0,
            }
        ],
    )

    process = run_verifier(tmp_path)

    assert process.returncode == 1
    assert "exited with 3" in process.stderr
    assert "bad" in process.stderr


def test_explicit_contract_override(tmp_path):
    write_contract(
        tmp_path / "contracts" / "default_verification_contract.json",
        [{"type": "file_exists", "path": "missing_default.txt"}],
    )
    override_contract = tmp_path / "custom_contract.json"
    write_contract(override_contract, [])

    process = run_verifier(tmp_path, "--contract", str(override_contract))

    assert process.returncode == 0, process.stderr


def test_workspace_contract_overrides_plugin_default(tmp_path):
    plugin_root = tmp_path / "plugin"
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    write_contract(
        plugin_root / "contracts" / "default_verification_contract.json",
        [{"type": "file_exists", "path": "plugin_missing.txt"}],
    )
    write_contract(
        workspace_root / "contracts" / "default_verification_contract.json",
        [],
    )

    process = run_verifier(
        workspace_root,
        env={"CLAUDE_PLUGIN_ROOT": str(plugin_root)},
    )

    assert process.returncode == 0, process.stderr


def test_plugin_default_used_when_workspace_contract_missing(tmp_path):
    plugin_root = tmp_path / "plugin"
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    write_contract(
        plugin_root / "contracts" / "default_verification_contract.json",
        [{"type": "file_exists", "path": "plugin_missing.txt"}],
    )

    process = run_verifier(
        workspace_root,
        env={"CLAUDE_PLUGIN_ROOT": str(plugin_root)},
    )

    assert process.returncode == 1
    assert "plugin_missing.txt" in process.stderr


def test_failure_output_is_globally_capped(tmp_path):
    checks = [
        {
            "type": "file_exists",
            "path": f"missing_{idx}_{'x' * 200}.txt",
        }
        for idx in range(200)
    ]
    write_contract(
        tmp_path / "contracts" / "default_verification_contract.json",
        checks,
    )

    process = run_verifier(tmp_path)

    assert process.returncode == 1
    assert len(process.stderr) <= 10050
    assert len(process.stderr.splitlines()) <= 101
