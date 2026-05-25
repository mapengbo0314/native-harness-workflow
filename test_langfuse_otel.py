import os
from langfuse.decorators import langfuse_context

os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "https://cloud.langfuse.com/api/public/otel"
os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = "Authorization=Basic%20dummy"
os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
os.environ.pop("LANGFUSE_SECRET_KEY", None)

try:
    langfuse_context.update_current_trace(tags=["test"])
    import logging
    print("Langfuse Context SDK initialized successfully")
except Exception as e:
    print("Error:", e)
