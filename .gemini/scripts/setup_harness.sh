#!/usr/bin/env bash
set -e

# Check for indxr API keys
if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  Warning: indxr requires an ANTHROPIC_API_KEY or OPENAI_API_KEY for background wiki updates."
    echo "Background auto-indexing will be disabled until a key is exported in your terminal."
    echo "Example: export ANTHROPIC_API_KEY='sk-ant-...' "
    echo ""
fi

echo "=== Setting up Superpowers for Gemini CLI ==="
if command -v gemini &> /dev/null; then
    echo "Adding indxr to Gemini CLI project MCP configuration..."
    indxr_serve_args_str="serve --watch --wiki-auto-update --all-tools"
    gemini mcp add indxr bash -c "cd '/Users/pengbolicious/pengbo-apps/e-2-g' && indxr $indxr_serve_args_str" -e GEMINI_API_KEY=\$GEMINI_API_KEY -e ANTHROPIC_API_KEY=\$ANTHROPIC_API_KEY -e OPENAI_API_KEY=\$OPENAI_API_KEY || true
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
echo "Setup complete. To activate indxr in Gemini, run Gemini from the project root and use '/mcp reload'."
