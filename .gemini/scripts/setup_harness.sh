#!/usr/bin/env bash
set -e

echo "=== Setting up Superpowers for Gemini CLI ==="
if command -v gemini &> /dev/null; then
    echo "Ensuring CodeGraph is built..."
    CODEGRAPH_DEBUG=1 npx -y @colbymchenry/codegraph init --index || true

    echo "Adding codegraph to Gemini CLI project MCP configuration..."
    gemini mcp add codegraph npx -y @colbymchenry/codegraph serve --mcp || true
else
    echo "Warning: gemini command not found."
fi

echo ""
echo "=== Setting up Superpowers for Claude Code ==="
if command -v claude &> /dev/null; then
    # Local skills are already in .claude/skills/ if needed
    echo "Claude Code configuration complete."
else
    echo "Warning: claude command not found."
fi

echo ""
echo "Setup complete. To activate codegraph in Gemini, run Gemini from the project root and use '/mcp reload'."
