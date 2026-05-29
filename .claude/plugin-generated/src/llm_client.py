import os
import uuid
import json
import subprocess
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langfuse import observe

# Langfuse v4 compatibility - inline compat for plugin-generated version
from langfuse import get_client as _get_client
class _LangfuseContextCompat:
    def __init__(self):
        self._client = _get_client()
    def update_current_observation(self, model=None, input=None, output=None, metadata=None,
                                   input_tokens=None, output_tokens=None, usage=None,
                                   usage_details=None, **kwargs):
        if usage_details is None:
            if input_tokens is not None or output_tokens is not None:
                usage_details = {}
                if input_tokens is not None:
                    usage_details["input"] = input_tokens
                if output_tokens is not None:
                    usage_details["output"] = output_tokens
            elif usage is not None:
                usage_details = {}
                if usage.get("input_tokens") is not None:
                    usage_details["input"] = usage["input_tokens"]
                elif usage.get("input") is not None:
                    usage_details["input"] = usage["input"]
                if usage.get("output_tokens") is not None:
                    usage_details["output"] = usage["output_tokens"]
                elif usage.get("output") is not None:
                    usage_details["output"] = usage["output"]
        self._client.update_current_generation(model=model, input=input, output=output,
                                               metadata=metadata, usage_details=usage_details, **kwargs)
    def update_current_trace(self, session_id=None, tags=None, metadata=None, **kwargs):
        merged_metadata = metadata or {}
        if session_id is not None:
            merged_metadata['session_id'] = session_id
        if tags is not None:
            merged_metadata['tags'] = tags
        self._client.update_current_span(metadata=merged_metadata, **kwargs)
    def get_current_trace_id(self):
        return self._client.get_current_trace_id()
    def get_current_observation_id(self):
        return self._client.get_current_observation_id()
    def flush(self):
        self._client.flush()
langfuse_context = _LangfuseContextCompat()

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
    """Dispatches to the real LLM providers via their native CLIs."""
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
                input=prompt, capture_output=True, text=True, check=True, timeout=30, env=env
            )
            data = json.loads(result.stdout)
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
                input=prompt, capture_output=True, text=True, check=True, timeout=30, env=env
            )
            data = json.loads(result.stdout)
            stats = data.get("stats", {}).get("models", {})
            actual_model = next(iter(stats.keys()), "gemini-unknown")
            tokens_data = stats.get(actual_model, {}).get("tokens", {})

            last_actual_model = actual_model
            langfuse_context.update_current_observation(
                model=actual_model,
                usage_details={
                    "input": tokens_data.get("prompt", 0),
                    "output": tokens_data.get("candidates", 0),
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
