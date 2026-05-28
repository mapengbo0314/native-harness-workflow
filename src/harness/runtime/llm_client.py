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
