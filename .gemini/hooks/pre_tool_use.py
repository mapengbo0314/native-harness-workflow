#!/usr/bin/env python3
import json
import sys
import re
from pathlib import Path
from hook_common import resolve_plugin_root

def is_dangerous_rm_command(command):
    """
    Comprehensive detection of dangerous rm commands.
    Matches various forms of rm -rf and similar destructive patterns.
    """
    normalized = ' '.join(command.lower().split())
    
    patterns = [
        r'\brm\s+.*-[a-z]*r[a-z]*f',
        r'\brm\s+.*-[a-z]*f[a-z]*r',
        r'\brm\s+--recursive\s+--force',
        r'\brm\s+--force\s+--recursive',
        r'\brm\s+-r\s+.*-f',
        r'\brm\s+-f\s+.*-r',
    ]
    
    for pattern in patterns:
        if re.search(pattern, normalized):
            return True
            
    dangerous_paths = [
        r'/', r'/\*', r'~', r'~/', r'\$HOME', r'\.\.', r'\*', r'\.', r'\.\s*$'
    ]
    
    if re.search(r'\brm\s+.*-[a-z]*r', normalized):
        for path in dangerous_paths:
            if re.search(path, normalized):
                return True
                
    return False

def is_env_file_access(tool_name, tool_input):
    """
    Check if any tool is trying to access .env files containing sensitive data.
    Supports both Claude Code and Gemini CLI tool names.
    """
    file_tools = ['Read', 'Edit', 'MultiEdit', 'Write', 'read_file', 'write_file', 'replace']
    bash_tools = ['Bash', 'run_shell_command']
    
    if tool_name in file_tools:
        file_path = tool_input.get('file_path', '')
        if '.env' in file_path and not file_path.endswith('.env.sample'):
            return True
            
    if tool_name in bash_tools:
        command = tool_input.get('command', '')
        env_patterns = [
            r'\b\.env\b(?!\.sample)',
            r'cat\s+.*\.env\b(?!\.sample)',
            r'echo\s+.*>\s*\.env\b(?!\.sample)',
            r'touch\s+.*\.env\b(?!\.sample)',
            r'cp\s+.*\.env\b(?!\.sample)',
            r'mv\s+.*\.env\b(?!\.sample)'
        ]
        
        for pattern in env_patterns:
            if re.search(pattern, command):
                return True
                
    return False

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
        
        if is_env_file_access(tool_name, tool_input):
            print("BLOCKED: Access to .env files containing sensitive data is prohibited", file=sys.stderr)
            print("Use .env.sample for template files instead", file=sys.stderr)
            if is_gemini:
                print(json.dumps({"decision": "deny", "reason": "Access to .env files containing sensitive data is prohibited"}))
                sys.exit(0)
            else:
                sys.exit(2)
        
        if tool_name in ['Bash', 'run_shell_command']:
            command = tool_input.get('command', '')
            if is_dangerous_rm_command(command):
                print("BLOCKED: Dangerous rm command detected and prevented", file=sys.stderr)
                if is_gemini:
                    print(json.dumps({"decision": "deny", "reason": "Dangerous rm command detected and prevented"}))
                    sys.exit(0)
                else:
                    sys.exit(2)
        
        # Ensure log directory exists
        log_dir = resolve_plugin_root() / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / 'pre_tool_use.json'
        
        log_data = []
        if log_path.exists():
            try:
                with open(log_path, 'r') as f:
                    log_data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                log_data = []
        
        log_data.append(input_data)
        
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)
            
        if is_gemini:
            print(json.dumps({}))
            sys.exit(0)
        else:
            sys.exit(0)
            
    except Exception as e:
        # Fallback empty response for Gemini to not break execution loop
        if 'input_str' in locals() and 'hook_event_name' in input_str:
            print(json.dumps({}))
        sys.exit(0)

if __name__ == '__main__':
    main()
