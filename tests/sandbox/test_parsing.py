import json
from typing import List, Dict, Any, Optional
import re

def parse_tool_calls(text: str) -> List[Dict[str, Any]]:
    """Robustly parse multiple tool calls from text."""
    results = []
    
    # Pre-process text to remove common markdown formatting that might interfere with regex
    # but keep ```json blocks for specialized parsing if needed.
    
    # Pattern to find potential JSON objects. 
    # We look for something that starts with { and contains "tool", "name", or "call"
    # and ends with } matching braces.
    
    # We'll use the same brace-counting logic but collect all matches.
    i = 0
    while i < len(text):
        # Look for {
        if text[i] == '{':
            start_idx = i
            brace_count = 1
            j = i + 1
            while j < len(text) and brace_count > 0:
                if text[j] == '{':
                    brace_count += 1
                elif text[j] == '}':
                    brace_count -= 1
                j += 1
            
            if brace_count == 0:
                potential_json = text[start_idx:j]
                try:
                    data = json.loads(potential_json)
                    # Check if it looks like a tool call
                    name = data.get("tool") or data.get("name") or data.get("call")
                    args = data.get("arguments") or data.get("args") or data.get("input") or data.get("parameters") or {}
                    if name:
                        results.append({"name": name, "arguments": args})
                except json.JSONDecodeError:
                    pass
                # Advance i to j-1 to continue searching after this block
                i = j - 1
        i += 1
    
    return results

def test_parse_simple():
    text = '{"tool": "read_file", "arguments": {"file_path": "test.txt"}}'
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "read_file"
    assert calls[0]["arguments"] == {"file_path": "test.txt"}

def test_parse_markdown():
    text = 'Here is the file:\n```json\n{"tool": "read_file", "arguments": {"file_path": "test.txt"}}\n```'
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "read_file"

def test_parse_multiple():
    text = 'First I read:\n{"tool": "read_file", "arguments": {"file_path": "a.txt"}}\nThen I write:\n{"name": "write_file", "args": {"file_path": "b.txt", "content": "hi"}}'
    calls = parse_tool_calls(text)
    assert len(calls) == 2
    assert calls[0]["name"] == "read_file"
    assert calls[1]["name"] == "write_file"
    assert calls[1]["arguments"] == {"file_path": "b.txt", "content": "hi"}

def test_parse_variations():
    text = '{"call": "grep_search", "parameters": {"pattern": "TODO"}}'
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "grep_search"
    assert calls[0]["arguments"] == {"pattern": "TODO"}

if __name__ == "__main__":
    test_parse_simple()
    test_parse_markdown()
    test_parse_multiple()
    test_parse_variations()
    print("All tests passed!")
