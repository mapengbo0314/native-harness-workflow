import json
import os
import tempfile
from pathlib import Path
from tests.sandbox.analytics import generate_report

def test_generate_report():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        events_file = tmp_path / "events.json"
        output_file = tmp_path / "report.md"
        
        # Create mock events
        events = [
            {"timestamp": "2023-10-01T10:00:00", "event_type": "SESSION_START", "data": {"prompt": "Hello world"}},
            {"timestamp": "2023-10-01T10:00:01", "event_type": "HOOK_END", "data": {"hook": "prompt_interceptor", "branch": "B"}},
            {"timestamp": "2023-10-01T10:00:05", "event_type": "LLM_RESPONSE", "data": {"text": "I will help you."}},
            {"timestamp": "2023-10-01T10:00:10", "event_type": "TOOL", "data": {"tool_name": "read_file", "tool_args": {"file_path": "test.txt"}}},
            {"timestamp": "2023-10-01T10:00:15", "event_type": "SAFETY_VIOLATION", "data": {"hook": "pre_tool_guard", "tool_name": "run_shell_command", "reason": "[VIOLATION] sudo blocked"}},
            {"timestamp": "2023-10-01T10:00:20", "event_type": "SESSION_END", "data": {"status": "finished"}}
        ]        
        with open(events_file, 'w') as f:
            for e in events:
                f.write(json.dumps(e) + '\n')
                
        # Generate report
        generate_report(str(events_file), str(output_file))
        
        # Verify report
        assert output_file.exists()
        content = output_file.read_text()
        
        assert "# Harness Audit Master Report" in content
        assert "Total User Characters | 11" in content
        assert "Total LLM Response Characters | 16" in content
        assert "Actual Routed Branch | **B**" in content
        assert "read_file | 1" in content
        assert "[VIOLATION] sudo blocked" in content
        assert "Harness Tax" in content
        assert "Theoretical Token Savings" in content

if __name__ == "__main__":
    try:
        test_generate_report()
        print("✅ Analytics test passed!")
    except Exception as e:
        print(f"❌ Analytics test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
