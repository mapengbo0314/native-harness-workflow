#!/bin/bash
set -e

# Default LLM
LLM="gemini"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --llm) LLM="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

echo "1. Minting fresh workspace with new hook (LLM: $LLM)..."
HARNESS_HEADLESS=1 HARNESS_PLATFORM=2 python src/harness/cli.py init --project-path . --llm "$LLM"

# Source .env if it exists to load golden keys
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Map golden keys for headless testing
export LANGFUSE_PUBLIC_KEY="${HARNESS_GOLDEN_LANGFUSE_PUBLIC_KEY:-$LANGFUSE_PUBLIC_KEY}"
export LANGFUSE_SECRET_KEY="${HARNESS_GOLDEN_LANGFUSE_SECRET_KEY:-$LANGFUSE_SECRET_KEY}"
export LANGFUSE_HOST="${HARNESS_GOLDEN_LANGFUSE_HOST:-$LANGFUSE_HOST}"

echo -e "\n2. Testing Branch D (Surgical Edit)"
echo '{"prompt": "Fix the typo in README", "cwd": "'$(pwd)'"}' | python .claude/plugin-generated/hooks/prompt_classifier.py

echo -e "\n3. Testing Branch B (Feature Request)"
echo '{"prompt": "Implement a new authentication system", "cwd": "'$(pwd)'"}' | python .claude/plugin-generated/hooks/prompt_classifier.py

echo -e "\n4. Testing Fallback Logic"
# Unset keys to force failure in the LLM dispatcher
env -u GEMINI_API_KEY -u ANTHROPIC_API_KEY -u OPENAI_API_KEY echo '{"prompt": "There is a bug in the code", "cwd": "'$(pwd)'"}' | python .claude/plugin-generated/hooks/prompt_classifier.py

echo -e "\n5. Cleaning up test artifacts..."
rm -rf .claude
rm -rf .claude.backup.*
rm -rf .harness_tmp

echo -e "\nAll tests completed and artifacts cleaned up. Check Langfuse to verify traces for steps 2 and 3."
