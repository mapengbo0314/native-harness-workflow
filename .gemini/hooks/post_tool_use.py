#!/usr/bin/env python3
import json
import sys
import os
import subprocess
from pathlib import Path

def get_formatter_command(file_path: Path) -> list[list[str]]:
    """Return a list of subprocess commands to run for the given file type."""
    ext = file_path.suffix.lower()
    
    # Python
    if ext == '.py':
        return [
            ['ruff', 'format', str(file_path)],
            ['ruff', 'check', '--fix', str(file_path)]
        ]
    
    # JavaScript / TypeScript / JSON / Markdown
    elif ext in ['.js', '.jsx', '.ts', '.tsx', '.json', '.md']:
        # Prefer prettier if available, fallback to nothing if not in path (simplistic approach)
        # In a real environment, you might check shutil.which('prettier')
        return [
            ['npx', 'prettier', '--write', str(file_path)]
        ]
        
    return []

def main():
    try:
        input_str = sys.stdin.read()
        if not input_str.strip():
            # For Gemini, output {}
            print(json.dumps({}))
            sys.exit(0)
            
        input_data = json.loads(input_str)
        
        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})
        is_gemini = "hook_event_name" in input_data
        
        # Only intercept specific modifying tools
        target_tools = ['write_file', 'replace', 'Edit', 'Write']
        if tool_name not in target_tools:
            if is_gemini:
                print(json.dumps({}))
            sys.exit(0)
            
        # Extract file path depending on tool schema
        file_path_str = tool_input.get('file_path') or tool_input.get('path') or tool_input.get('file')
        if not file_path_str:
            if is_gemini:
                print(json.dumps({}))
            sys.exit(0)
            
        file_path = Path(file_path_str)
        if not file_path.exists():
            if is_gemini:
                print(json.dumps({}))
            sys.exit(0)
            
        # Determine commands and run them silently
        commands = get_formatter_command(file_path)
        for cmd in commands:
            try:
                subprocess.run(
                    cmd, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL, 
                    check=False
                )
            except Exception as e:
                # Swallow exceptions to not crash the hook
                print(f"Linter warning: failed to run {' '.join(cmd)}: {e}", file=sys.stderr)
        
        if is_gemini:
            print(json.dumps({}))
            sys.exit(0)
            
    except Exception as e:
        print(f"Post-tool-use hook error: {e}", file=sys.stderr)
        # Fallback empty response for Gemini
        if 'input_str' in locals() and 'hook_event_name' in input_str:
            print(json.dumps({}))
        sys.exit(0)

if __name__ == '__main__':
    main()
