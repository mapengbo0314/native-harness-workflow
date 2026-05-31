import os
import sys

hooks_dir = ".claude/harness-wf-plugin/src/hooks"

hook_header_old = """import sys, os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import datetime
import traceback

def log_action(hook_name, action, details=""):
    \"\"\"Log action to harness.log.\"\"\"
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../config'))
    log_file = os.path.join(config_dir, 'harness.log')
    timestamp = datetime.datetime.now().isoformat()
    pid = os.getpid()
    
    # Ensure config dir exists
    os.makedirs(config_dir, exist_ok=True)
    
    try:
        with open(log_file, 'a') as f:
            f.write(f"[{timestamp}] [PID:{pid}] [{hook_name}] {action} - {details}\\n")
    except Exception:
        pass"""

hook_header_new = """import sys, os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import datetime
import traceback

def log_action(hook_name, action, details=""):
    \"\"\"Log action to harness.log.\"\"\"
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../config'))
    log_file = os.path.join(config_dir, 'harness.log')
    timestamp = datetime.datetime.now().isoformat()
    pid = os.getpid()
    
    # Ensure config dir exists
    os.makedirs(config_dir, exist_ok=True)
    
    log_line = f"[{timestamp}] [PID:{pid}] [{hook_name}] {action} - {details}\\n"
    
    try:
        with open(log_file, 'a') as f:
            f.write(log_line)
    except Exception:
        pass
        
    if os.environ.get("DEBUG_HARNESS") == "1":
        print(log_line, file=sys.stderr, end="")"""

files_with_exceptions = ["prompt_interceptor.py", "pre_tool_guard.py", "stop_monitor.py"]
all_hooks = ["prompt_interceptor.py", "pre_tool_guard.py", "post_tool_monitor.py", "precompact_monitor.py", "stop_monitor.py"]

for filename in all_hooks:
    filepath = os.path.join(hooks_dir, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Replace header
        content = content.replace(hook_header_old, hook_header_new)
        
        # Replace exceptions if needed
        if filename in files_with_exceptions:
            # We construct the regex or find/replace for the exception block
            old_exc = f'''    except Exception as e:
        print(f"[HOOK CRASH]: {filename.split(".")[0]} failed: {{e}}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)'''
            
            new_exc = f'''    except Exception as e:
        print(f"[HOOK CRASH]: {filename.split(".")[0]} failed: {{e}}", file=sys.stderr)
        print(f"[HOOK CRASH]: sys.argv={{sys.argv}}", file=sys.stderr)
        try:
            if not sys.stdin.isatty():
                stdin_data = sys.stdin.read()
                if stdin_data:
                    print(f"[HOOK CRASH]: stdin={{stdin_data}}", file=sys.stderr)
        except Exception:
            pass
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)'''
            
            content = content.replace(old_exc, new_exc)
            
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Patched {filename}")
