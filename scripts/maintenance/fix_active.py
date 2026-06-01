import os
import glob

hook_files = glob.glob(".claude/harness-wf-plugin/src/hooks/*.py")

for hook_file in hook_files:
    if os.path.basename(hook_file) in ['__init__.py']:
        continue
        
    with open(hook_file, 'r') as f:
        content = f.read()
        
    if "import traceback" not in content:
        content = content.replace("import sys", "import sys\nimport traceback", 1)
        
    if "try:" not in content.split("if __name__ == ")[-1]:
        # Wrap the whole main block
        lines = content.split("if __name__ == \"__main__\":\n")
        if len(lines) > 1:
            main_block = lines[1]
            indented_main = "\n".join(["    " + line for line in main_block.split("\n")])
            new_main = f"""    try:
{indented_main}
    except Exception as e:
        print(f"[HOOK CRASH]: {{e}}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)"""
            content = lines[0] + "if __name__ == \"__main__\":\n" + new_main
            
            with open(hook_file, 'w') as f:
                f.write(content)
            print(f"Patched main block in {hook_file}")

