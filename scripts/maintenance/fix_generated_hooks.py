import re

pre_tool = ".claude/harness-wf-plugin/src/hooks/pre_tool_guard.py"
stop_mon = ".claude/harness-wf-plugin/src/hooks/stop_monitor.py"

try:
    with open(pre_tool, 'r') as f:
        content = f.read()
    
    # Fix broken quotes if any
    content = content.replace(' guidance."", file=sys.stderr)', ' guidance.", file=sys.stderr)')
    
    if "[REJECTED]" not in content:
        old_reject_block = """        if rejections >= 3:
            print("[ESCALATION]: You are stuck. Use ask_user to ask for human guidance.", file=sys.stderr)
            
        log_action("pre_tool_guard", "reject", f"Tool {tool_name} rejected ({rejections} rejections)")
        sys.exit(1)"""

        new_reject_block = """        print(f"[REJECTED]: Tool {tool_name} was rejected. Please review constraints.", file=sys.stderr)
        if rejections >= 3:
            print("[ESCALATION]: You are stuck. Use ask_user to ask for human guidance.", file=sys.stderr)
            
        log_action("pre_tool_guard", "reject", f"Tool {tool_name} rejected ({rejections} rejections)")
        sys.exit(1)"""
        
        # also try the version without file=sys.stderr
        old_reject_block_2 = """        if rejections >= 3:
            print("[ESCALATION]: You are stuck. Use ask_user to ask for human guidance.")
            
        log_action("pre_tool_guard", "reject", f"Tool {tool_name} rejected ({rejections} rejections)")
        sys.exit(1)"""
        
        if old_reject_block in content:
            content = content.replace(old_reject_block, new_reject_block)
        elif old_reject_block_2 in content:
            content = content.replace(old_reject_block_2, new_reject_block)
            
    with open(pre_tool, 'w') as f:
        f.write(content)
    print("Fixed pre_tool_guard.py")
except FileNotFoundError:
    pass

try:
    with open(stop_mon, 'r') as f:
        content = f.read()
        
    # Ensure file=sys.stderr
    content = re.sub(
        r'print\(f"\[GATEKEEPER ERROR\]: \{result\.stderr or result\.stdout\}"\)',
        r'print(f"[GATEKEEPER ERROR]: {result.stderr or result.stdout}", file=sys.stderr)',
        content
    )
    with open(stop_mon, 'w') as f:
        f.write(content)
    print("Fixed stop_monitor.py")
except FileNotFoundError:
    pass
