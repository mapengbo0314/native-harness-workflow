import os
import uuid
import json
import subprocess
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langfuse import observe
from harness.runtime.langfuse_compat import langfuse_context

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

            # Extract model from response (e.g., "claude-haiku-4-5-20251001")
            actual_model = next(iter(data.get("modelUsage", {}).keys()), "claude-unknown")

            # Track tokens in Langfuse
            usage = data.get("usage", {})
            langfuse_context.update_current_observation(
                model=actual_model,
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens")
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
            langfuse_context.update_current_observation(
                model=actual_model,
                input_tokens=tokens_data.get("prompt"),
                output_tokens=tokens_data.get("candidates")
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
