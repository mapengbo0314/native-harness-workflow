from __future__ import annotations

import json
from pathlib import Path

from benchmark.clawbench_v2.adapters.base import BaseAdapter
from benchmark.clawbench_v2.adapters.claude_code import classify_claude_failure
from benchmark.clawbench_v2.models import AdapterRunContext, AdapterRunResult, AppConfig
from benchmark.clawbench_v2.runner import run_task
from benchmark.clawbench_v2.tasks import load_tasks


def test_claude_rate_limit_is_classified() -> None:
    failure = classify_claude_failure(
        "You've hit your limit · resets 6:20pm (America/Toronto)",
        "",
        1,
    )

    assert failure["error_type"] == "rate_limit"
    assert failure["retryable"] is True


def test_claude_empty_nonzero_exit_is_classified() -> None:
    failure = classify_claude_failure("", "", 1)

    assert failure["error_type"] == "empty_cli_failure"
    assert failure["retryable"] is False


class _StdoutAdapter(BaseAdapter):
    name = "stdout_adapter"

    def run(self, ctx: AdapterRunContext) -> AdapterRunResult:
        return AdapterRunResult(
            ok=True,
            command=["stdout-adapter"],
            stdout="real adapter transcript",
            stderr="",
            metadata={"returncode": 0},
        )


class _NoopUsageProxy:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.base_url = "http://127.0.0.1:9"

    def __enter__(self) -> "_NoopUsageProxy":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_runner_persists_real_adapter_stdout(monkeypatch, tmp_path: Path) -> None:
    task_dir = tmp_path / "tasks" / "stdout-task"
    fixtures_dir = task_dir / "fixtures"
    fixtures_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text(
        json.dumps(
            {
                "task_id": "stdout-task",
                "title": "stdout task",
                "prompt_file": "prompt.txt",
                "fixtures_dir": "fixtures",
                "oracle_module": "oracle_grade.py",
            }
        ),
        encoding="utf-8",
    )
    (task_dir / "prompt.txt").write_text("Do the task.\n", encoding="utf-8")
    (task_dir / "oracle_grade.py").write_text(
        "from pathlib import Path\n"
        "def score_workspace(workspace: Path) -> dict:\n"
        "    return {'outcome_score': 1.0, 'passed': True}\n",
        encoding="utf-8",
    )

    tasks = load_tasks(tmp_path / "tasks")
    app = AppConfig(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        tasks_dir=tmp_path / "tasks",
        results_dir=tmp_path / "results",
        work_root=tmp_path / "work",
    )
    app.data_dir.mkdir()
    app.results_dir.mkdir()
    app.work_root.mkdir()

    monkeypatch.setattr(
        "benchmark.clawbench_v2.runner.build_adapter",
        lambda _name: _StdoutAdapter(),
    )
    monkeypatch.setattr("benchmark.clawbench_v2.runner.UsageProxy", _NoopUsageProxy)

    run_task(
        app,
        tasks["stdout-task"],
        "stdout-model",
        {"adapter": "stdout_adapter"},
        "live",
        keep_workspace=False,
    )

    result = json.loads((tmp_path / "results" / "stdout-model" / "stdout-task.json").read_text())
    assert result["adapter_result"]["stdout"] == "real adapter transcript"
    assert result["proxy_trace"]["error"] == "missing responses/"
