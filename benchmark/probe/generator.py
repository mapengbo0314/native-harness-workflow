from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

INPUT_VALUE = 7
MULTIPLIER = 3
ADDEND = 2

_LAYERS: list[tuple[str, str]] = [
    ("pipeline",      "run_pipeline"),
    ("ingestion",     "ingest_record"),
    ("validation",    "validate_entry"),
    ("enrichment",    "enrich_data"),
    ("aggregation",   "aggregate_values"),
    ("normalization", "normalize_output"),
    ("formatting",    "format_result"),
    ("serialization", "serialize_payload"),
    ("compression",   "compress_data"),
    ("encryption",    "encrypt_payload"),
]

MIN_DEPTH = 1
MAX_DEPTH = len(_LAYERS) - 1


@dataclass(frozen=True)
class ChainSpec:
    depth: int
    input_value: int = INPUT_VALUE


def expected_output(spec: ChainSpec) -> int:
    return spec.input_value * MULTIPLIER


def _intermediate_layer_source(module_name: str, func_name: str, next_module: str, next_func: str) -> str:
    return (
        "from __future__ import annotations\n"
        f"from src import {next_module}\n"
        "\n"
        "\n"
        f"def {func_name}(value: int) -> int:\n"
        f"    return {next_module}.{next_func}(value)\n"
    )


def _bug_layer_source(func_name: str) -> str:
    return (
        "from __future__ import annotations\n"
        "\n"
        "\n"
        f"def {func_name}(value: int) -> int:\n"
        f"    return value + {ADDEND}\n"
    )


def _test_source(entry_func: str, expected: int) -> str:
    return (
        "from src.pipeline import run_pipeline\n"
        "\n"
        "\n"
        "def test_pipeline_output() -> None:\n"
        f"    result = run_pipeline({INPUT_VALUE})\n"
        f"    assert result == {expected}, f\"Expected {expected}, got {{result}}\"\n"
    )


def _readme_source() -> str:
    return (
        "# Probe Workspace\n\n"
        "A pipeline with a failing test, run pytest tests/ -v\n"
    )


def generate_workspace(spec: ChainSpec, out_dir: Path) -> None:
    if not (MIN_DEPTH <= spec.depth <= MAX_DEPTH):
        raise ValueError(f"depth must be between {MIN_DEPTH} and {MAX_DEPTH}, got {spec.depth}")

    src_dir = out_dir / "src"
    tests_dir = out_dir / "tests"
    src_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)

    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")

    layers = _LAYERS[: spec.depth + 1]

    for i, (module_name, func_name) in enumerate(layers):
        is_bug_layer = i == spec.depth
        if is_bug_layer:
            source = _bug_layer_source(func_name)
        else:
            next_module, next_func = layers[i + 1]
            source = _intermediate_layer_source(module_name, func_name, next_module, next_func)
        (src_dir / f"{module_name}.py").write_text(source, encoding="utf-8")

    entry_func = layers[0][1]
    (tests_dir / "test_entry.py").write_text(
        _test_source(entry_func, expected_output(spec)), encoding="utf-8"
    )
    (out_dir / "README.md").write_text(_readme_source(), encoding="utf-8")
