import os
import uuid
import json
import subprocess
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langfuse.decorators import observe, langfuse_context

@observe(as_type="generation")
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=5, max=20),
    retry=retry_if_exception_type(RuntimeError),
    before_sleep=lambda retry_state: print(f"Retrying LLM call (attempt {retry_state.attempt_number})..."),
    reraise=True
)
def query_llm(prompt: str, llm_provider: str, api_key: str, model: str = None) -> str:
    """Dispatches to the real LLM providers."""
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

    if llm_provider == "openai":
        from langfuse.openai import openai
        client = openai.OpenAI(api_key=api_key)
        use_model = model or "gpt-4o"
        response = client.chat.completions.create(
            model=use_model,
            messages=[{"role": "user", "content": prompt}]
        )
        if response.usage:
            langfuse_context.update_current_observation(
                usage={
                    "input": response.usage.prompt_tokens, 
                    "output": response.usage.completion_tokens
                }
            )
        return response.choices[0].message.content
        
    elif llm_provider == "anthropic":
        import urllib.request
        use_model = model or "claude-3-5-sonnet-20241022"
        data = {
            "model": use_model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(data).encode("utf-8"),
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
        )
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            
            usage = result.get("usage")
            if usage:
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                langfuse_context.update_current_observation(
                    model=use_model,
                    usage={"input": input_tokens, "output": output_tokens}
                )
                
            return result["content"][0]["text"]
            
    elif llm_provider == "gemini":
        from google import genai
        client = genai.Client(api_key=api_key)
        # Use a reliable default model
        use_model = model or "gemini-2.5-flash-lite"
        langfuse_context.update_current_observation(model=use_model)
        
        try:
            # We are using generate_content, which is synchronous. It might take 10-20 seconds.
            response = client.models.generate_content(
                model=use_model,
                contents=prompt
            )
            
            usage = getattr(response, "usage_metadata", None)
            if usage:
                input_tokens = getattr(usage, "prompt_token_count", 0)
                output_tokens = getattr(usage, "candidates_token_count", 0)
                langfuse_context.update_current_observation(
                    usage={"input": input_tokens, "output": output_tokens}
                )
                
            return response.text
        except Exception as e:
            raise RuntimeError(f"Gemini API call failed: {e}")

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
