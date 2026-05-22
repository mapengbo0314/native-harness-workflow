import re

with open('harness/plugin_generator.py', 'r') as f:
    content = f.read()

# Fix the GATEKEEPER ERROR print
content = re.sub(
    r'print\(f"\[GATEKEEPER ERROR\]: \{result\.stderr or result\.stdout\}"\)',
    r'print(f"[GATEKEEPER ERROR]: {result.stderr or result.stdout}", file=sys.stderr)',
    content
)

# Fix the ESCALATION print and add a generic REJECTED print
old_reject_block = """        if rejections >= 3:
            print("[ESCALATION]: You are stuck. Use ask_user to ask for human guidance.")
            
        log_action("pre_tool_guard", "reject", f"Tool {tool_name} rejected ({rejections} rejections)")
        sys.exit(1)"""

new_reject_block = """        print(f"[REJECTED]: Tool {tool_name} was rejected. Please review constraints.", file=sys.stderr)
        if rejections >= 3:
            print("[ESCALATION]: You are stuck. Use ask_user to ask for human guidance.", file=sys.stderr)
            
        log_action("pre_tool_guard", "reject", f"Tool {tool_name} rejected ({rejections} rejections)")
        sys.exit(1)"""

content = content.replace(old_reject_block, new_reject_block)

# Clean up any broken quotes from fix_stderr
content = content.replace(' guidance."", file=sys.stderr)', ' guidance.", file=sys.stderr)')

with open('harness/plugin_generator.py', 'w') as f:
    f.write(content)

print("Fixed harness/plugin_generator.py")
