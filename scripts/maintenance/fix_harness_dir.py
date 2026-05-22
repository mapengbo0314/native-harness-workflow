import re
with open("harness/minting_engine.py", "r") as f:
    content = f.read()

# Make sure that when reading agent templates, we replace {{HARNESS_DIR}} with the target_dir name (e.g. .claude or .gemini)
replacement_logic = """
            with open(agent_md_path, "w") as f:
                f.write(agent_content)
"""

new_logic = """
            agent_content = agent_content.replace("{{HARNESS_DIR}}", platform_dir_name)
            with open(agent_md_path, "w") as f:
                f.write(agent_content)
"""
if "{{HARNESS_DIR}}" not in content:
    content = content.replace(replacement_logic, new_logic)
    with open("harness/minting_engine.py", "w") as f:
        f.write(content)
    print("Fixed minting_engine.py for HARNESS_DIR")
