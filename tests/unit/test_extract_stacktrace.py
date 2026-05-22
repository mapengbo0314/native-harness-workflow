import os
import subprocess
import tempfile
import sys

def test_python_traceback_extraction():
    log_content = """
Some noisy pytest setup logs
...
Traceback (most recent call last):
  File "/workspace/my_project/tests/test_feature.py", line 42, in test_broken_thing
    assert calculate(5) == 10
AssertionError: assert 5 == 10
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        f.write(log_content)
        log_path = f.name

    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'src', 'harness', 'templates', 'boilerplate', 'scripts', 'extract_stacktrace.py')
    
    try:
        result = subprocess.run([sys.executable, script_path, log_path], capture_output=True, text=True)
        output = result.stdout
        assert "AssertionError: assert 5 == 10" in output
        assert "/workspace/my_project/tests/test_feature.py" in output
    finally:
        os.remove(log_path)

def test_rust_panic_extraction():
    log_content = """
thread 'main' panicked at 'assertion failed: `(left == right)`', src/main.rs:2:5
stack backtrace:
   2: my_rust_app::main
             at ./src/main.rs:2:5
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        f.write(log_content)
        log_path = f.name

    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'src', 'harness', 'templates', 'boilerplate', 'scripts', 'extract_stacktrace.py')
    
    try:
        result = subprocess.run([sys.executable, script_path, log_path], capture_output=True, text=True)
        output = result.stdout
        assert "panicked at 'assertion failed" in output
        assert "src/main.rs:2:5" in output
    finally:
        os.remove(log_path)

def test_node_error_extraction():
    log_content = """
Error: Something went wrong
    at Object.<anonymous> (/workspace/app.js:2:13)
    at Module._compile (internal/modules/cjs/loader.js:1159:14)
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        f.write(log_content)
        log_path = f.name

    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'src', 'harness', 'templates', 'boilerplate', 'scripts', 'extract_stacktrace.py')
    
    try:
        result = subprocess.run([sys.executable, script_path, log_path], capture_output=True, text=True)
        output = result.stdout
        assert "Error: Something went wrong" in output
        assert "at Object.<anonymous>" in output
    finally:
        os.remove(log_path)

def test_java_exception_extraction():
    log_content = """
Exception in thread "main" java.lang.NullPointerException: Cannot invoke "String.length()"
    at com.example.Main.main(Main.java:5)
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        f.write(log_content)
        log_path = f.name

    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'src', 'harness', 'templates', 'boilerplate', 'scripts', 'extract_stacktrace.py')
    
    try:
        result = subprocess.run([sys.executable, script_path, log_path], capture_output=True, text=True)
        output = result.stdout
        assert "java.lang.NullPointerException" in output
        assert "at com.example.Main.main" in output
    finally:
        os.remove(log_path)
