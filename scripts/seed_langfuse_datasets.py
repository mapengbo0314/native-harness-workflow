#!/usr/bin/env python3
import os
import json
from dotenv import load_dotenv

load_dotenv()

def main():
    # Map golden keys to standard Langfuse variables for seeding
    if os.getenv("HARNESS_GOLDEN_LANGFUSE_PUBLIC_KEY"):
        os.environ["LANGFUSE_PUBLIC_KEY"] = os.getenv("HARNESS_GOLDEN_LANGFUSE_PUBLIC_KEY")
    if os.getenv("HARNESS_GOLDEN_LANGFUSE_SECRET_KEY"):
        os.environ["LANGFUSE_SECRET_KEY"] = os.getenv("HARNESS_GOLDEN_LANGFUSE_SECRET_KEY")
    if os.getenv("HARNESS_GOLDEN_LANGFUSE_HOST"):
        os.environ["LANGFUSE_HOST"] = os.getenv("HARNESS_GOLDEN_LANGFUSE_HOST")

    has_keys = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
    if not has_keys:
        print("Langfuse credentials missing. Skipping dataset seeding.")
        return

    from langfuse import Langfuse
    langfuse = Langfuse()

    dataset_name = os.environ.get("LANGFUSE_DATASET_NAME", "harness_test_dataset")
    print(f"Creating or fetching Langfuse dataset: {dataset_name}")
    
    langfuse.create_dataset(name=dataset_name)
    
    dataset_path = os.path.join(os.path.dirname(__file__), "..", "evals", "test_dataset.jsonl")
    if not os.path.exists(dataset_path):
        print(f"Dataset file not found: {dataset_path}")
        return

    with open(dataset_path, "r") as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            item = json.loads(line)
            langfuse.create_dataset_item(
                dataset_name=dataset_name,
                input=item.get("input"),
                expected_output=item.get("expected_output")
            )
            print(f"Inserted item {idx + 1}")
    
    print("Dataset seeding completed successfully.")

if __name__ == "__main__":
    main()
