import os
import uuid
import json
import subprocess
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langfuse import observe
from harness.runtime.langfuse_compat import langfuse_context

# Written by query_llm after each call so callers (classify_intent, dispatch_agent)
# can propagate the actual model name to their own Langfuse spans.
last_actual_model: str = ""


@observe(as_type="generation")
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=5, max=20),
    retry=retry_if_exception_type(RuntimeError),
    before_sleep=lambda retry_state: print(f"Retrying LLM call (attempt {retry_state.attempt_number})..."),
    reraise=True
)
def query_llm(prompt: str, cli_name: str, model: str = None) -> str:
    """Dispatches to the real LLM providers via their native CLIs with token tracking."""
    global last_actual_model
    trace_id = os.environ.get("LANGFUSE_TRACE_ID")
    if not trace_id:
        trace_id = str(uuid.uuid4())
        os.environ["LANGFUSE_TRACE_ID"] = trace_id

    session_id = os.environ.get("LANGFUSE_SESSION_ID")
    if not session_id:
        session_id = str(uuid.uuid4())
        os.environ["LANGFUSE_SESSION_ID"] = session_id

    tags = []
    if os.environ.get("HARNESS_EVAL_MODE") == "1":
        env_tags = os.environ.get("LANGFUSE_TAGS")
        tags = env_tags.split(",") if env_tags else ["integration-test"]

    langfuse_context.update_current_trace(session_id=session_id, tags=tags)

    # Prepare environment to strip ANSI colors
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env["CLAUDE_MD"] = "0"

    try:
        if cli_name == "claude":
            result = subprocess.run(
                ["claude", "--output-format=json", "-p", "-"],
                input=prompt,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
                env=env
            )
            data = json.loads(result.stdout)

            # modelUsage may contain multiple models (e.g. subagent calls); identify the
            # primary model by matching its outputTokens against the top-level usage field.
            model_usage_dict = data.get("modelUsage", {})
            top_output_tokens = data.get("usage", {}).get("output_tokens")
            actual_model = next(
                (
                    m for m, v in model_usage_dict.items()
                    if v.get("outputTokens") == top_output_tokens
                ),
                next(iter(model_usage_dict.keys()), "claude-unknown"),
            )
            model_tokens = model_usage_dict.get(actual_model, {})

            last_actual_model = actual_model
            langfuse_context.update_current_observation(
                model=actual_model,
                usage_details={
                    "input": model_tokens.get("inputTokens", 0),
                    "output": model_tokens.get("outputTokens", 0),
                    "cache_read_input": model_tokens.get("cacheReadInputTokens", 0),
                    "cache_creation_input": model_tokens.get("cacheCreationInputTokens", 0),
                }
            )

            return data.get("result", "")

        elif cli_name == "gemini":
            result = subprocess.run(
                ["gemini", "--output-format=json"],
                input=prompt,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
                env=env
            )
            data = json.loads(result.stdout)

            # Extract model and tokens from response
            stats = data.get("stats", {}).get("models", {})
            actual_model = next(iter(stats.keys()), "gemini-unknown")
            tokens_data = stats.get(actual_model, {}).get("tokens", {})

            # Track tokens in Langfuse
            last_actual_model = actual_model
            langfuse_context.update_current_observation(
                model=actual_model,
                usage={
                    "input": tokens_data.get("prompt"),
                    "output": tokens_data.get("candidates")
                }
            )

            return data.get("response", "")
        else:
            raise ValueError(f"Unsupported native CLI: {cli_name}")
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Native CLI {cli_name} timed out: {e}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Native CLI {cli_name} failed: {e.stderr or e.output or str(e)}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Native CLI {cli_name} returned invalid JSON: {e}")
    except Exception as e:
        raise RuntimeError(f"Native CLI {cli_name} execution error: {e}")
