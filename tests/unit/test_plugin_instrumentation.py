import os
import shutil
import tempfile
from pathlib import Path
from harness.plugin_generator import generate_orchestrator_plugin

def test_instrumentation_files_generated():
    project_root = Path(__file__).parent.parent.parent
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_project = Path(tmp_dir) / "test_project"
        tmp_project.mkdir()
        
        # Create minimal project structure
        (tmp_project / "docs" / "domain").mkdir(parents=True)
        (tmp_project / "docs" / "domain" / "CONTEXT.md").write_text("# Context")
        
        # Generate plugin
        plugin_dir = generate_orchestrator_plugin(str(tmp_project), "TestProject")
        
        plugin_path = Path(plugin_dir)
        src_dir = plugin_path / "src"
        
        # Check if instrumentation.py is copied
        assert (src_dir / "instrumentation.py").exists()
        
        # Check if prompt_interceptor.py has HOOK_START
        interceptor = src_dir / "hooks" / "prompt_interceptor.py"
        assert interceptor.exists()
        content = interceptor.read_text()
        assert 'logger.log_event("HOOK_START"' in content
        assert 'logger.log_event("HOOK_END"' in content
        
        # Check if pre_tool_guard.py has HOOK_START
        guard = src_dir / "hooks" / "pre_tool_guard.py"
        assert guard.exists()
        content = guard.read_text()
        assert 'logger.log_event("HOOK_START"' in content
        assert 'logger.log_event("HOOK_END"' in content

        # Check if post_tool_monitor.py has HOOK_START
        monitor = src_dir / "hooks" / "post_tool_monitor.py"
        assert monitor.exists()
        content = monitor.read_text()
        assert 'logger.log_event("HOOK_START"' in content
        assert 'logger.log_event("HOOK_END"' in content

        # Check if stop_monitor.py has HOOK_START
        stop = src_dir / "hooks" / "stop_monitor.py"
        assert stop.exists()
        content = stop.read_text()
        assert 'logger.log_event("HOOK_START"' in content
        assert 'logger.log_event("HOOK_END"' in content

if __name__ == "__main__":
    test_instrumentation_files_generated()
    print("Verification successful!")
