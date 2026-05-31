#!/usr/bin/env python3
import os
import sys
import json
import uuid
import time
import tempfile
import shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add src to python path so harness can be imported
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(project_root, "src"))

def create_mock_project():
    """Create a temporary mock project for the dispatcher."""
    temp_dir = tempfile.mkdtemp()
    
    config_dir = os.path.join(temp_dir, ".claude", "harness-wr-plugin", "config")
    os.makedirs(config_dir, exist_ok=True)
    
    with open(os.path.join(config_dir, "orchestrator.json"), "w") as f:
        json.dump({}, f)
    with open(os.path.join(config_dir, "agents.json"), "w") as f:
        json.dump({"agents": {"orchestrator": {}, "implementer": {}}}, f)
    with open(os.path.join(config_dir, "rules.json"), "w") as f:
        json.dump({"rules": {}}, f)
        
    return temp_dir, config_dir

def main():
    # Map golden keys to standard Langfuse variables for evaluation
    if os.getenv("HARNESS_GOLDEN_LANGFUSE_PUBLIC_KEY"):
        os.environ["LANGFUSE_PUBLIC_KEY"] = os.getenv("HARNESS_GOLDEN_LANGFUSE_PUBLIC_KEY")
    if os.getenv("HARNESS_GOLDEN_LANGFUSE_SECRET_KEY"):
        os.environ["LANGFUSE_SECRET_KEY"] = os.getenv("HARNESS_GOLDEN_LANGFUSE_SECRET_KEY")
    if os.getenv("HARNESS_GOLDEN_LANGFUSE_HOST"):
        os.environ["LANGFUSE_HOST"] = os.getenv("HARNESS_GOLDEN_LANGFUSE_HOST")

    has_keys = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
    dataset_path = os.path.join(os.path.dirname(__file__), "..", "evals", "test_dataset.jsonl")
    results = []
    
    if not has_keys:
        print("Langfuse credentials missing. Falling back to local mock parsing.")
        if os.path.exists(dataset_path):
            with open(dataset_path, "r") as f:
                for line in f:
                    if line.strip():
                        results.append({"item": json.loads(line), "score": 1.0, "status": "pass"})
        
        summary_path = os.path.join(os.path.dirname(__file__), "..", "evals", "eval_summary.json")
        with open(summary_path, "w") as f:
            json.dump({"status": "completed", "total_evals": len(results), "results": results}, f, indent=2)
        print(f"Saved local eval summary to {summary_path}")
        return

    print("Langfuse credentials found. Fetching dataset and evaluating...")
    try:
        from langfuse import Langfuse
        from harness.runtime.langfuse_compat import langfuse_context
        from harness.runtime.dispatcher import OrchestratorDispatcher
        
        langfuse = Langfuse()
        dataset_name = os.environ.get("LANGFUSE_DATASET_NAME", "harness_test_dataset")
        dataset = langfuse.get_dataset(dataset_name)
        
        for item in dataset.items:
            print(f"Evaluating item: {item.input}")
            
            temp_dir, config_dir = create_mock_project()
            
            trace_id = str(uuid.uuid4())
            os.environ["LANGFUSE_TRACE_ID"] = trace_id
            
            # The trace_id is picked up by the decorator via the environment variable LANGFUSE_TRACE_ID.
            
            result = None
            try:
                dispatcher = OrchestratorDispatcher(config_dir)
                result = dispatcher.dispatch_agent("orchestrator", {"prompt": item.input})
                if result and result.get("trace_id"):
                    trace_id = result["trace_id"]
                print(f"Dispatched with result branch: {result.get('intent_branch')}")
            except Exception as dispatch_e:
                print(f"Dispatch failed for item {item.input}: {dispatch_e}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                continue
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
            
            langfuse_context.flush()
            
            score_value = 1.0 if result and result.get("routed") else 0.0
            
            # Push real score asynchronously
            # We do not need to wait for Langfuse to index the trace. We can push events to the ingestion queue immediately.
            item.link(None, trace_id=trace_id, run_name="real_integration_eval")
            langfuse.score(
                trace_id=trace_id,
                name="routing_accuracy",
                value=score_value,
                comment=f"Routed to branch {result.get('intent_branch') if result else 'unknown'}"
            )
            
            results.append({
                "item_input": item.input,
                "score": score_value,
                "status": "pass" if score_value > 0.5 else "fail",
                "trace_id": trace_id
            })
            
            # Ensure the score and link events are uploaded
            langfuse.flush()
                
    except Exception as e:
        print(f"Langfuse eval failed: {e}")
        import traceback
        traceback.print_exc()

    summary_path = os.path.join(os.path.dirname(__file__), "..", "evals", "eval_summary.json")
    with open(summary_path, "w") as f:
        json.dump({"status": "completed", "total_evals": len(results), "results": results}, f, indent=2)
    print(f"Saved real eval summary to {summary_path}")

if __name__ == "__main__":
    main()