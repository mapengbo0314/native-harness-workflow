import pytest
from pathlib import Path
import tempfile
import shutil
from tests.sandbox.runner import ToolExecutionEngine

@pytest.fixture
def workspace():
    tmp_dir = tempfile.mkdtemp()
    workspace_path = Path(tmp_dir)
    yield workspace_path
    shutil.rmtree(tmp_dir)

def test_read_file_aliases(workspace):
    engine = ToolExecutionEngine(workspace)
    test_file = workspace / "test.txt"
    test_file.write_text("Hello World")
    
    # Test original
    assert engine.read_file(file_path="test.txt") == "Hello World"
    
    # Test aliases (these should fail currently or need manual arg extraction)
    # Note: ToolExecutionEngine.read_file(**args) is how it's called in MockHost._execute_tool
    
    # We want to support these:
    assert engine.read_file(path="test.txt") == "Hello World"
    assert engine.read_file(filename="test.txt") == "Hello World"
    assert engine.read_file(filepath="test.txt") == "Hello World"
    assert engine.read_file(file="test.txt") == "Hello World"

def test_write_file_aliases(workspace):
    engine = ToolExecutionEngine(workspace)
    
    engine.write_file(path="test_path.txt", content="path content")
    assert (workspace / "test_path.txt").read_text() == "path content"
    
    engine.write_file(filename="test_filename.txt", content="filename content")
    assert (workspace / "test_filename.txt").read_text() == "filename content"
    
    engine.write_file(filepath="test_filepath.txt", content="filepath content")
    assert (workspace / "test_filepath.txt").read_text() == "filepath content"

    engine.write_file(file="test_file.txt", content="file content")
    assert (workspace / "test_file.txt").read_text() == "file content"

def test_replace_aliases(workspace):
    engine = ToolExecutionEngine(workspace)
    test_file = workspace / "test.txt"
    test_file.write_text("Hello World")
    
    engine.replace(path="test.txt", old_string="Hello", new_string="Hi")
    assert test_file.read_text() == "Hi World"
    
    engine.replace(filename="test.txt", old_string="World", new_string="Universe")
    assert test_file.read_text() == "Hi Universe"

    engine.replace(file="test.txt", old_string="Hi", new_string="Greetings")
    assert test_file.read_text() == "Greetings Universe"

def test_grep_search_aliases(workspace):
    engine = ToolExecutionEngine(workspace)
    test_file = workspace / "test.txt"
    test_file.write_text("search me")
    
    # Grep search normally uses include_pattern
    # We want to support 'include' as well
    result = engine.grep_search(pattern="search", include="test.txt")
    assert "./test.txt:1:search me" in result

def test_missing_args_hardening(workspace):
    engine = ToolExecutionEngine(workspace)
    
    # grep_search without pattern
    assert "Error" in engine.grep_search(pattern=None)
    assert "Error" in engine.grep_search(pattern="")
    
    # run_shell_command without command
    res = engine.run_shell_command(command=None)
    assert "Error" in res["stderr"]
    
    # read_file without file_path
    assert "Error" in engine.read_file()
