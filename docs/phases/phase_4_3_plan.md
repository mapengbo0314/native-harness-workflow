# Scratchpad

## Context
- Goal: Enable native AI CLI tools (`claude` or `gemini`) for intent classification in the `OrchestratorDispatcher` when raw API keys are missing.
- Affected Files: 
  - `src/harness/discovery_engine.py` (update `query_llm` to support `native_cli`)
  - `src/harness/dispatcher.py` (update `classify_intent` to prioritize CLI checks)

## Design Doc
### Problem Statement
The Harness Discovery Engine requires explicit API keys (like `GEMINI_API_KEY`) to classify user intents and make LLM calls. We want to enable a zero-configuration "bring your own platform" capability by hooking into native AI CLIs already authenticated on the user's system, but we must do so safely (avoiding hangs, ANSI parsing failures, and bypassing explicit configurations).

### Proposed Design
1. **Update `query_llm`**: Add a `native_cli` provider block. We'll repurpose the `api_key` string to pass the executable name (e.g., `"claude"` or `"gemini"`). 
   - Use `subprocess.run` to execute the command.
   - Pass the prompt via `stdin` to avoid `ARG_MAX` OS length limits and argument injection attacks.
   - Set `env={"NO_COLOR": "1", "CLAUDE_MD": "0"}` (merged with `os.environ`) to prevent ANSI escape codes from destroying JSON parsing.
   - Set a strict `timeout=30` to prevent the Orchestrator from hanging on interactive prompts (like EULA acceptances).
   - Log the model to Langfuse without token usage (since usage isn't reliably available).
2. **Update `classify_intent`**: 
   - First, strictly check for `os.environ.get("GEMINI_API_KEY")`. If explicitly set, ALWAYS prioritize the fast HTTP API.
   - If (and only if) the API key is missing, check the environment variable `HARNESS_PLATFORM_CLI`. 
   - If not found, use `shutil.which` to see if `"claude"` or `"gemini"` are available in the PATH. Use this CLI via the `native_cli` provider. 
   - If no CLI is present, or if the subprocess execution times out/fails, fall back to keyword parsing.

### Alternatives
- **Modifying `query_llm` Signature**: We could add a new `cli_name` parameter to avoid hijacking `api_key`. However, keeping the signature intact prevents cascading breaks across the discovery codebase.
- **Direct config parsing**: We could attempt to read local CLI auth configs directly, but this is brittle across OS updates and CLI versions. Executing the CLI binary relies on their existing, supported authentication boundaries.

### Sphinch Marks
- [ ] `src/harness/discovery_engine.py` imports `subprocess` and `os`.
- [ ] `query_llm` handles `elif llm_provider == "native_cli"`.
- [ ] `subprocess.run` executes `["claude", "-p", "-"]` or `["gemini"]` and passes the prompt via `input` (stdin).
- [ ] `subprocess.run` includes `timeout=30` and strips ANSI colors via `env`.
- [ ] `langfuse_context.update_current_observation` traces `model=f"native-cli-{cli_name}"`.
- [ ] `src/harness/dispatcher.py` prioritizes `GEMINI_API_KEY` BEFORE checking `shutil.which`.

## Plan
### Step 1: Modify `src/harness/discovery_engine.py`
Update `query_llm` to support the `native_cli` provider using `subprocess`.

**Target File:** `src/harness/discovery_engine.py`
**Changes to `query_llm`:**
```python
import subprocess
import os

# In query_llm(prompt: str, llm_provider: str, api_key: str, model: str = None) -> str:
    # ... existing openai, anthropic, gemini logic ...

    elif llm_provider == "native_cli":
        cli_name = api_key  # We use api_key param to pass the CLI binary name
        langfuse_context.update_current_observation(model=f"native-cli-{cli_name}")
        
        # Prepare environment to strip ANSI colors
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        env["CLAUDE_MD"] = "0"
        
        try:
            if cli_name == "claude":
                # claude -p reads from stdin if prompt is not fully provided, but -p - forces stdin reading
                result = subprocess.run(["claude", "-p", "-"], input=prompt, capture_output=True, text=True, check=True, timeout=30, env=env)
                return result.stdout
            elif cli_name == "gemini":
                # gemini CLI also accepts piping
                result = subprocess.run(["gemini"], input=prompt, capture_output=True, text=True, check=True, timeout=30, env=env)
                return result.stdout
            else:
                raise ValueError(f"Unsupported native CLI: {cli_name}")
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Native CLI {cli_name} timed out: {e}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Native CLI {cli_name} failed: {e.stderr or e.output or str(e)}")
        except Exception as e:
            raise RuntimeError(f"Native CLI {cli_name} execution error: {e}")

    raise ValueError(f"Unsupported LLM provider: {llm_provider}")
```

### Step 2: Modify `src/harness/dispatcher.py`
Update `classify_intent` to prioritize the API key, and only fall back to CLI discovery if the key is missing.

**Target File:** `src/harness/dispatcher.py`
**Changes to `classify_intent`:**
```python
import shutil
import os

# In class OrchestratorDispatcher:
    @observe(as_type="span")
    def classify_intent(self, prompt: str) -> Dict[str, str]:
        # ... keep docstring ...
        
        classification_prompt = f"""
Analyze the following user prompt and classify it into one of the following Matrix Routing Branches:
... (keep existing prompt definition) ...
}}
"""
        api_key = os.environ.get("GEMINI_API_KEY")
        cli_name = None
        
        if not api_key:
            cli_name = os.environ.get("HARNESS_PLATFORM_CLI")
            if not cli_name:
                if shutil.which("claude"):
                    cli_name = "claude"
                elif shutil.which("gemini"):
                    cli_name = "gemini"
        
        if query_llm and (api_key or cli_name):
            try:
                if api_key:
                    model = os.environ.get("HARNESS_MODEL", "gemini-2.5-flash-lite")
                    response = query_llm(classification_prompt, "gemini", api_key, model=model)
                else:
                    response = query_llm(classification_prompt, "native_cli", api_key=cli_name)
                
                # Extract JSON
                cleaned = response.replace("```json", "").replace("```", "").strip()
                # ... (keep existing extraction logic)
```

## Verification
- Test that setting `HARNESS_PLATFORM_CLI=claude` triggers a subprocess call when `GEMINI_API_KEY` is not set.
- Test that omitting both, but having `claude` in the path (mocked `shutil.which`), appropriately calls the `native_cli` provider.
- Test that fallback keywords still work if both CLI commands fail and `GEMINI_API_KEY` is not set.
