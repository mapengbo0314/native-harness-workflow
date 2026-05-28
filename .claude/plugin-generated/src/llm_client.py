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
    def update_current_observation(self, model=None, **kwargs):
        self._client.update_current_generation(model=model, **kwargs)
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
