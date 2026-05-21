#!/usr/bin/env bash
set -e
cd /Users/pengbolicious/pengbo-apps/e-2-g
echo "=== Setting up Superpowers for Claude Code ==="
PLUGIN_READY=0
CODEGRAPH_READY=0

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ACTION REQUIRED] python3 is required but was not found."
    exit 1
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 8):
    raise SystemExit("[ACTION REQUIRED] Python 3.8+ is required.")
print(f"Python runtime OK: {sys.version.split()[0]}")
PY

echo "Running generated plugin smoke test..."
python3 - <<'PY'
import importlib
import json
import sys
from pathlib import Path

plugin = Path(".claude/plugin-generated")
required = [
    plugin / ".claude-plugin" / "plugin.json",
    plugin / "src" / "dispatcher.py",
    plugin / "src" / "hooks" / "prompt_interceptor.py",
    plugin / "src" / "hooks" / "pre_tool_guard.py",
    plugin / "src" / "hooks" / "post_tool_monitor.py",
    plugin / "src" / "hooks" / "precompact_monitor.py",
    plugin / "src" / "hooks" / "stop_monitor.py",
    plugin / "config" / "ddd-context.json",
    plugin / "agents",
    plugin / "skills",
    plugin / "scripts" / "gatekeeper.py",
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    print("[ACTION REQUIRED] Generated plugin payload is incomplete:")
    for path in missing:
        print(f"  - {path}")
    raise SystemExit(1)

sys.path.insert(0, str(plugin))
importlib.import_module("src.dispatcher")
json.loads((plugin / "config" / "ddd-context.json").read_text())
print("Plugin payload smoke test OK.")
PY

echo "To install Skills for Claude Code workspace-wide, run these commands inside the Claude Code interface:"
echo "  /plugin install orchestrator-plugin@local-plugin --project"


# Orchestrator Plugin Installation
if [ -d ".claude/plugin-generated" ]; then
    echo "Checking for non-interactive Claude Code plugin install support..."
    if command -v claude >/dev/null 2>&1 && claude plugin --help >/dev/null 2>&1; then
        if claude plugin marketplace add "$PWD/.claude/plugin-generated" --scope project && claude plugin install orchestrator-plugin@local-orchestrator-marketplace --scope project; then
            PLUGIN_READY=1
            echo "Orchestrator plugin installed automatically."
        else
            echo "[ACTION REQUIRED] Automatic plugin installation failed."
        fi
    else
        echo "[ACTION REQUIRED] Claude Code plugin CLI automation was not detected."
    fi

    if [ "$PLUGIN_READY" != "1" ]; then
        echo "[ACTION REQUIRED] Open Claude Code in this repo and run:"
        echo "  /plugin marketplace add "\$PWD/.claude/plugin-generated" --scope project"
        echo "  /plugin install orchestrator-plugin@local-orchestrator-marketplace --scope project"
        echo "Restart or reload Claude Code if hooks/tools do not appear immediately."
    fi
fi

# MCP Configuration for Claude via .mcp.json
echo "Ensuring CodeGraph is built..."
npx -y @colbymchenry/codegraph init --index || true

echo "Generating repo-level .mcp.json..."
cat << 'MCPJSON' > .mcp.json
{
  "mcpServers": {
    "codegraph": {
      "command": "npx",
      "args": [
        "-y",
        "@colbymchenry/codegraph",
        "serve",
        "--mcp"
      ]
    },
    "fetch": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-server-fetch-typescript"
      ]
    },
    "git-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-git"
      ]
    }
  }
}
MCPJSON
CODEGRAPH_READY=1
echo "✅ MCP servers configured in .mcp.json"


python3 - <<PY
import json
import os
import sys
import time
from pathlib import Path

config = Path(".claude/plugin-generated/config")
config.mkdir(parents=True, exist_ok=True)
state_file = config / ".harness_state.json"
tmp_file = config / ".harness_state.tmp.json"
lock_dir = config / ".harness_state.json.lock"

start = time.time()
while True:
    try:
        lock_dir.mkdir()
        break
    except FileExistsError:
        if time.time() - start > 5:
            raise SystemExit("[ACTION REQUIRED] Could not acquire harness state lock.")
        time.sleep(0.05)

try:
    state = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
        except json.JSONDecodeError:
            state = {}
    state.update({
        "setup_complete": True,
        "python_version": sys.version.split()[0],
        "codegraph_ready": os.environ.get("CODEGRAPH_READY", "$CODEGRAPH_READY") == "1",
        "plugin_install_manual_steps_printed": os.environ.get("PLUGIN_READY", "$PLUGIN_READY") != "1",
        "strict_enforcement_enabled": os.environ.get("CODEGRAPH_READY", "$CODEGRAPH_READY") == "1",
    })
    tmp_file.write_text(json.dumps(state, indent=2))
    os.replace(tmp_file, state_file)
finally:
    try:
        lock_dir.rmdir()
    except OSError:
        pass
PY

if [ "$CODEGRAPH_READY" = "1" ]; then
    echo "Harness setup complete. Strict enforcement is ready after plugin activation."
else
    echo "[ACTION REQUIRED] Harness setup did not complete CodeGraph readiness; strict enforcement remains disabled."
fi
