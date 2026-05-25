#!/bin/bash
set -e

echo "1. Minting fresh workspace with new hook..."
HARNESS_HEADLESS=1 HARNESS_PLATFORM=2 python src/harness/cli.py init --project-path . --llm gemini

echo -e "\n2. Testing Branch D (Surgical Edit)"
echo '{"prompt": "Fix the typo in README", "cwd": "'$(pwd)'"}' | python .claude/plugin-generated/hooks/prompt_classifier.py

echo -e "\n3. Testing Branch B (Feature Request)"
echo '{"prompt": "Implement a new authentication system", "cwd": "'$(pwd)'"}' | python .claude/plugin-generated/hooks/prompt_classifier.py

echo -e "\n4. Testing Fallback Logic"
# Unset key to force failure in the LLM dispatcher
env -u GEMINI_API_KEY echo '{"prompt": "There is a bug in the code", "cwd": "'$(pwd)'"}' | python .claude/plugin-generated/hooks/prompt_classifier.py

echo -e "\nAll tests completed. Check Langfuse to verify traces for steps 2 and 3."