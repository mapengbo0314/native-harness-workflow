import os

def test_core_mandates_file_exists():
    assert os.path.exists("boilerplate-agent/rules/core_mandates.md"), "Core mandates file is missing"
