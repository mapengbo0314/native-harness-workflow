import os
import uuid
from dotenv import load_dotenv
from langfuse.decorators import observe, langfuse_context

load_dotenv()

@observe()
def test_trace():
    print(f"Current trace ID: {langfuse_context.get_current_trace_id()}")

if __name__ == "__main__":
    trace_id = str(uuid.uuid4())
    os.environ["LANGFUSE_TRACE_ID"] = trace_id
    print(f"Set env trace ID: {trace_id}")
    test_trace()
    langfuse_context.flush()
