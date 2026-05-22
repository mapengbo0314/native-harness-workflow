import os
import re
import pytest
from pathlib import Path

def get_maintenance_scripts():
    maintenance_dir = Path("scripts/maintenance")
    if not maintenance_dir.exists():
        return []
    return list(maintenance_dir.glob("*.py"))

@pytest.mark.parametrize("script_path", get_maintenance_scripts())
def test_maintenance_script_paths_exist(script_path):
    with open(script_path, "r") as f:
        content = f.read()
    
    # Find all strings that look like paths starting with tests/
    # e.g. "tests/test_dynamic_manifest.py" or 'tests/something'
    paths = re.findall(r'["\'](tests/[^"\']+)["\']', content)
    
    for path_str in paths:
        # Check if the path exists relative to the project root
        assert Path(path_str).exists(), f"Path '{path_str}' in {script_path} does not exist!"

def test_benchmarks_moved():
    # Verify benchmarks are in the new location
    benchmark_dir = Path("tests/benchmarks")
    expected_benchmarks = [
        "benchmark_gate.py",
        "benchmark_hub_vs_spoke.py",
        "efficiency_suite.py"
    ]
    for b in expected_benchmarks:
        assert (benchmark_dir / b).exists(), f"Benchmark {b} not found in tests/benchmarks/"
    
    # Verify they are no longer in scripts/
    scripts_dir = Path("scripts")
    for b in expected_benchmarks:
        assert not (scripts_dir / b).exists(), f"Benchmark {b} still exists in scripts/"
