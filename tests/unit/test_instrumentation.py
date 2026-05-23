import os
import json
import tempfile
from pathlib import Path
import pytest
from harness.instrumentation import HarnessEventLogger

def test_logger_writes_json_line():
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        os.environ["HARNESS_INSTRUMENTATION_FILE"] = tmp_path
        logger = HarnessEventLogger()
        logger.log_event("TEST_EVENT", {"foo": "bar"})
        
        with open(tmp_path, 'r') as f:
            line = f.readline()
            data = json.loads(line)
            assert data["event_type"] == "TEST_EVENT"
            assert data["data"]["foo"] == "bar"
            assert "timestamp" in data
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if "HARNESS_INSTRUMENTATION_FILE" in os.environ:
            del os.environ["HARNESS_INSTRUMENTATION_FILE"]

def test_logger_silent_if_no_env():
    if "HARNESS_INSTRUMENTATION_FILE" in os.environ:
        del os.environ["HARNESS_INSTRUMENTATION_FILE"]
    
    logger = HarnessEventLogger()
    # Should not raise exception
    logger.log_event("TEST_EVENT", {"foo": "bar"})

def test_logger_handles_file_error_gracefully(tmp_path):
    # Create a directory where a file should be, to cause an error
    bad_path = tmp_path / "not_a_file"
    bad_path.mkdir()
    
    os.environ["HARNESS_INSTRUMENTATION_FILE"] = str(bad_path)
    logger = HarnessEventLogger()
    # Should not raise exception even if file write fails
    logger.log_event("TEST_EVENT", {"foo": "bar"})
    
    if "HARNESS_INSTRUMENTATION_FILE" in os.environ:
        del os.environ["HARNESS_INSTRUMENTATION_FILE"]
