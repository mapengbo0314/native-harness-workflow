import os
import uuid
from harness.dispatcher import OrchestratorDispatcher
from langfuse.decorators import langfuse_context

os.environ["GEMINI_API_KEY"] = "mock"
os.environ["LANGFUSE_TRACE_ID"] = str(uuid.uuid4())

print("Set trace ID:", os.environ["LANGFUSE_TRACE_ID"])
