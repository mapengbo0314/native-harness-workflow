import os
import re

hooks_dir = ".claude/harness-wf-plugin/src/hooks"
all_hooks = ["prompt_interceptor.py", "pre_tool_guard.py", "post_tool_monitor.py", "precompact_monitor.py", "stop_monitor.py"]

log_action_pattern = r'def log_action.*?except Exception:\s*pass'
log_action_replacement = '''def log_action(hook_name, action, details=""):
    """Log action to harness.log."""
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
        print(log_line, file=sys.stderr, end="")'''

exc_pattern = r'except Exception as e:\s*print\(f"\[HOOK CRASH\]:.*?", file=sys\.stderr\)\s*traceback\.print_exc\(file=sys\.stderr\)\s*sys\.exit\(1\)'

for filename in all_hooks:
    filepath = os.path.join(hooks_dir, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Replace log_action
        content = re.sub(log_action_pattern, log_action_replacement, content, flags=re.DOTALL)
        
        # Replace except Exception
        hook_base = filename.split(".")[0]
        exc_replacement = f'''except Exception as e:
        print(f"[HOOK CRASH]: {hook_base} failed: {{e}}", file=sys.stderr)
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
        content = re.sub(exc_pattern, exc_replacement, content, flags=re.DOTALL)
        
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Patched {filename}")
