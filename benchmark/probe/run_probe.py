from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BENCHMARK_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BENCHMARK_DIR.parent
if str(BENCHMARK_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_DIR))
repo_src = str(REPO_ROOT / "src")
if repo_src not in sys.path:
    sys.path.insert(0, repo_src)

os.environ.setdefault("CLAWBENCHV2_APP_CONFIG", str(BENCHMARK_DIR / "config" / "app.yaml"))
os.environ.setdefault("CLAWBENCHV2_MODELS_CONFIG", str(BENCHMARK_DIR / "config" / "models.yaml"))
os.environ.setdefault("CLAWBENCHV2_PROJECT_ROOT", str(REPO_ROOT))

from clawbench_v2.config import load_app_config, load_model_config
from clawbench_v2.models import TaskSpec
from clawbench_v2.runner import run_task

_HOOKS_TEMPLATE = '''\
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "benchmark"))
from probe.generator import ChainSpec, generate_workspace
from probe.scrambler import Scrambler
import yaml

def prepare_runtime(state: dict) -> dict:
    task = state["task"]
    workspace = Path(state["workspace"])
    task_dir = Path(task.task_dir)
    params = yaml.safe_load((task_dir / "task.yaml").read_text())["probe"]
    generate_workspace(ChainSpec(depth=int(params["depth"])), workspace)
    clarity = float(params["clarity"])
    if clarity < 1.0:
        Scrambler(seed=int(params["seed"])).scramble_workspace(workspace, clarity)
    return {}
'''

_ORACLE_TEMPLATE = '''\
from __future__ import annotations
import subprocess, sys
from pathlib import Path

def score_workspace(workspace: Path) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short", "-q"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=60,
    )
    passed = result.returncode == 0
    return {
        "outcome_score": 1.0 if passed else 0.0,
        "passed": passed,
        "pytest_output": (result.stdout + result.stderr)[:3000],
        "pytest_returncode": result.returncode,
    }
'''

_PROMPT = "The test suite is failing. Find the root cause and fix it.\n\nRun: pytest tests/ -v\n"

_TASK_YAML_TEMPLATE = """\
task_id: "{task_id}"
title: "Probe depth={depth} clarity={clarity} rep={rep}"
prompt_file: "prompt.txt"
oracle_module: "oracle_grade.py"
hooks_module: "hooks.py"
timeout_sec: 300
tags: ["probe"]
probe:
  depth: {depth}
  clarity: {clarity}
  seed: {seed}
"""


@dataclass
class RunRecord:
    model: str
    depth: int
    clarity: float
    rep: int
    outcome_score: float
    elapsed_sec: float
    ok: bool


def _seed_for(depth: int, clarity: float, rep: int, model_id: str) -> int:
    key = f"{model_id}|{depth}|{clarity:.6f}|{rep}"
    return sum((i + 1) * ord(ch) for i, ch in enumerate(key)) % (2**31)


def _make_temp_task(depth: int, clarity: float, rep: int, model_id: str) -> Path:
    task_dir = Path(tempfile.mkdtemp(prefix="probe-task-"))
    task_id = f"probe-d{depth}-c{clarity}-r{rep}-{model_id.replace('/', '-')}"
    seed = _seed_for(depth, clarity, rep, model_id)
    (task_dir / "task.yaml").write_text(
        _TASK_YAML_TEMPLATE.format(
            task_id=task_id, depth=depth, clarity=clarity, rep=rep, seed=seed
        ),
        encoding="utf-8",
    )
    (task_dir / "prompt.txt").write_text(_PROMPT, encoding="utf-8")
    (task_dir / "hooks.py").write_text(_HOOKS_TEMPLATE, encoding="utf-8")
    (task_dir / "oracle_grade.py").write_text(_ORACLE_TEMPLATE, encoding="utf-8")
    (task_dir / "fixtures").mkdir()
    return task_dir


def _make_task_spec(task_dir: Path) -> TaskSpec:
    import yaml  # type: ignore

    data = yaml.safe_load((task_dir / "task.yaml").read_text(encoding="utf-8"))
    return TaskSpec(
        task_id=str(data["task_id"]),
        title=str(data.get("title", data["task_id"])),
        prompt_file=str(data.get("prompt_file", "prompt.txt")),
        prompt_files=[str(x) for x in (data.get("prompt_files") or [])],
        fixtures_dir=str(data.get("fixtures_dir", "fixtures")),
        oracle_module=str(data.get("oracle_module", "oracle_grade.py")),
        hooks_module=str(data.get("hooks_module", "hooks.py")),
        timeout_sec=int(data.get("timeout_sec", 300)),
        tags=list(data.get("tags", []) or []),
        task_dir=task_dir.resolve(),
    )


def _run_one(
    app: Any,
    model_id: str,
    model_cfg: dict[str, Any],
    mode: str,
    depth: int,
    clarity: float,
    rep: int,
) -> RunRecord:
    task_dir = _make_temp_task(depth, clarity, rep, model_id)
    task = _make_task_spec(task_dir)
    start = time.monotonic()
    result = run_task(app, task, model_id, model_cfg, mode, keep_workspace=False)
    elapsed = time.monotonic() - start
    outcome_score = float(result.oracle_result.get("outcome_score", 0.0))
    return RunRecord(
        model=model_id,
        depth=depth,
        clarity=clarity,
        rep=rep,
        outcome_score=outcome_score,
        elapsed_sec=elapsed,
        ok=result.adapter_result.ok,
    )


def _print_table(records: list[RunRecord], models: list[str], mode: str) -> None:
    dry = mode == "dry"
    print("\n=== Probe Dry-Run Wiring Check ===" if dry else "\n=== Probe Results ===")
    if dry:
        print("Dry mode skips the agent; this table reports adapter setup success, not task pass rate.")
    metric_label = "adapter_ok" if dry else "pass_rate"
    header = f"{'depth':<6} {'clarity':<8} {'model':<32} {metric_label:<10} {'n'}"
    print(header)

    depths = sorted({r.depth for r in records})
    clarities = sorted({r.clarity for r in records}, reverse=True)

    for depth in depths:
        for clarity in clarities:
            for model in models:
                subset = [
                    r for r in records
                    if r.depth == depth and r.clarity == clarity and r.model == model
                ]
                if not subset:
                    continue
                passed = (
                    sum(1 for r in subset if r.ok)
                    if dry
                    else sum(1 for r in subset if r.outcome_score >= 1.0)
                )
                total = len(subset)
                pct = int(100 * passed / total) if total else 0
                print(
                    f"{depth:<6} {clarity:<8} {model:<32} {passed}/{total:<9} {pct}%"
                )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run probe benchmark")
    parser.add_argument("--models", required=True, help="Comma-separated model IDs")
    parser.add_argument("--depths", required=True, help="Comma-separated depths")
    parser.add_argument("--clarities", required=True, help="Comma-separated clarity floats")
    parser.add_argument("--reps", type=int, default=1, help="Repetitions per combination")
    parser.add_argument("--mode", default="live", help="Adapter mode (live/dry)")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    models = [m.strip() for m in args.models.split(",")]
    depths = [int(d.strip()) for d in args.depths.split(",")]
    clarities = [float(c.strip()) for c in args.clarities.split(",")]
    for clarity in clarities:
        if not 0.0 <= clarity <= 1.0:
            raise SystemExit(f"clarity must be between 0.0 and 1.0, got {clarity}")

    app = load_app_config()
    all_model_cfgs = load_model_config()

    records: list[RunRecord] = []

    for model_id in models:
        model_cfg = all_model_cfgs.get(model_id, {})
        for depth in depths:
            for clarity in clarities:
                for rep in range(1, args.reps + 1):
                    print(
                        f"Running model={model_id} depth={depth} clarity={clarity} rep={rep}",
                        flush=True,
                    )
                    record = _run_one(
                        app, model_id, model_cfg, args.mode, depth, clarity, rep
                    )
                    records.append(record)
                    print(
                        f"  -> outcome_score={record.outcome_score} elapsed={record.elapsed_sec:.1f}s",
                        flush=True,
                    )

    _print_table(records, models, args.mode)


if __name__ == "__main__":
    main()
