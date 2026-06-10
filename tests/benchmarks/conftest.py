"""Make the flat `clawbench_v2` package importable (it lives under benchmark/).

clawbench_v2 modules import each other as `clawbench_v2.*` (see
benchmark/run.py, which does the same sys.path insertion), so tests must
import it under that single canonical name — never via `benchmark.clawbench_v2`,
which would create a second module instance.
"""
import sys
from pathlib import Path

_BENCH_DIR = str(Path(__file__).resolve().parents[2] / "benchmark")
if _BENCH_DIR not in sys.path:
    sys.path.insert(0, _BENCH_DIR)
