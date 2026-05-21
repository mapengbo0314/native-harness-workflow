import re

with open("harness/minting_engine.py", "r") as f:
    content = f.read()

# 1. We replace the way mcp_installs is populated
old_loop = """    elif active_platform == "claude":
        for s in selected_skills:
            if s.get('type') == 'extension':
                 skill_installs += f'echo "  /plugin install {s["name"]}@{s["url"]} --project"\\n'
        for m in selected_mcps:
            cmd = m["command"]
            if " " in cmd:
                cmd = f'bash -c {shlex.quote(cmd)}'
            mcp_installs += f'    claude mcp add {m["name"]} -- {cmd} || true\\n'"""

new_loop = """    elif active_platform == "claude":
        for s in selected_skills:
            if s.get('type') == 'extension':
                 skill_installs += f'echo "  /plugin install {s["name"]}@{s["url"]} --project"\\n'
        # We handle MCP installs below by generating .mcp.json directly"""

content = content.replace(old_loop, new_loop)

# 2. We replace the bash block that calls claude mcp add
old_bash = """# MCP Configuration for Claude
if command -v claude &> /dev/null; then
    echo "Ensuring CodeGraph is built..."
    npx -y @colbymchenry/codegraph init --index

    echo "Adding codegraph to Claude Code project MCP configuration..."
    claude mcp add --scope project codegraph -- npx -y @colbymchenry/codegraph serve --mcp
    CODEGRAPH_READY=1
{mcp_installs}
else
    echo "[ACTION REQUIRED] claude command not found; CodeGraph MCP could not be registered."
fi"""

new_bash = """# MCP Configuration for Claude via .mcp.json
echo "Ensuring CodeGraph is built..."
npx -y @colbymchenry/codegraph init --index || true

echo "Generating repo-level .mcp.json..."
cat << 'MCPJSON' > .mcp.json
{mcp_json_content}
MCPJSON
CODEGRAPH_READY=1
echo "✅ MCP servers configured in .mcp.json"
"""

content = content.replace(old_bash, new_bash)

# 3. We need to actually generate the {mcp_json_content} in the script
# Find where scripts_to_generate is defined
scripts_def = "    scripts_to_generate = {"
new_scripts_def = """    import json
    mcp_config_dict = {
        "mcpServers": {
            "codegraph": {
                "command": "npx",
                "args": ["-y", "@colbymchenry/codegraph", "serve", "--mcp"]
            }
        }
    }
    if active_platform == "claude":
        for m in selected_mcps:
            parts = m["command"].split(" ")
            mcp_config_dict["mcpServers"][m["name"]] = {
                "command": parts[0],
                "args": parts[1:]
            }
    
    mcp_json_str = json.dumps(mcp_config_dict, indent=2)

    scripts_to_generate = {"""

content = content.replace(scripts_def, new_scripts_def)

# 4. Replace {mcp_json_content} in the format call
old_format = """        "claude": f\"\"\"#!/usr/bin/env bash"""
# Actually, since it's an f-string, it will format {mcp_json_content} automatically if it's in scope.

with open("harness/minting_engine.py", "w") as f:
    f.write(content)

print("minting_engine.py updated")
