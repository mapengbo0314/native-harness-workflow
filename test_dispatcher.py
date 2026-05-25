import os
import sys
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Check keys
print("Keys loaded:")
print("PUBLIC:", os.environ.get("LANGFUSE_PUBLIC_KEY"))
print("SECRET:", os.environ.get("LANGFUSE_SECRET_KEY")[:10] + "..." if os.environ.get("LANGFUSE_SECRET_KEY") else None)
print("HOST:", os.environ.get("LANGFUSE_HOST"))

# Initialize Langfuse natively
from langfuse.decorators import langfuse_context, observe

@observe()
def test_func():
    langfuse_context.update_current_trace(tags=["test_harness_project"])
    print("Trace context updated")

try:
    test_func()
    langfuse_context.flush()
    print("Flush completed")
except Exception as e:
    print("Error:", e)
