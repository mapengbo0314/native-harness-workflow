import os
import sys
import argparse
import re

def check_phase_1_ready(workspace_path):
    """Verifies that Phase 1 (Discovery) is authorized via a Diagnosis Report for bugs."""
    diagnosis_path = os.path.join(workspace_path, "artifacts", "diagnosis_report.md")
    if not os.path.exists(diagnosis_path):
        print(f"GATEKEEPER FAILURE: {diagnosis_path} is missing. You MUST perform a diagnosis before discovery.")
        sys.exit(1)
    
    with open(diagnosis_path, 'r') as f:
        content = f.read()
        if "Root Cause" not in content and "reproducible" not in content.lower():
            print(f"GATEKEEPER FAILURE: {diagnosis_path} lacks a clear Root Cause or reproduction steps.")
            sys.exit(1)
    print("PASS: Diagnosis verified.")
    sys.exit(0)

def check_phase_3_ready(workspace_path):
    """Verifies that Phase 3 (Verification) is authorized via a plan with Sphinch Marks."""
    plan_path = os.path.join(workspace_path, "artifacts", "implementation_plan.md")
    if not os.path.exists(plan_path):
        # Fallback to general artifacts/plan.md or artifacts/implementation_plan.md
        plan_path = os.path.join(workspace_path, "artifacts", "plan.md")
        if not os.path.exists(plan_path):
            print(f"GATEKEEPER FAILURE: No implementation plan found in artifacts/.")
            sys.exit(1)

    with open(plan_path, 'r') as f:
        content = f.read()
        if "## Sphinch Marks" not in content and "## Verification Criteria" not in content:
            print(f"GATEKEEPER FAILURE: Plan in {plan_path} is missing strict Verification Criteria (Sphinch Marks).")
            sys.exit(1)
    print("PASS: Plan structure verified.")
    sys.exit(0)

def check_phase_4_ready(workspace_path):
    """
    Ensures that Phase 4 (Execution) is authorized by verifying:
    1. A plan exists in artifacts/implementation_plan.md or plan.md.
    2. A failing test log exists in artifacts/tdd_failing_test.log and contains a valid failure.
    """
    plan_path = os.path.join(workspace_path, "artifacts", "implementation_plan.md")
    if not os.path.exists(plan_path):
        plan_path = os.path.join(workspace_path, "artifacts", "plan.md")
    
    test_log_path = os.path.join(workspace_path, "artifacts", "tdd_failing_test.log")

    errors = []

    # 1. Check for Implementation Plan
    if not os.path.exists(plan_path):
        errors.append(f"MISSING ARTIFACT: {plan_path} (Required for Phase 4)")
    else:
        print(f"PASS: Found {plan_path}")

    # 2. Check for TDD Failing Test Log
    if not os.path.exists(test_log_path):
        errors.append(f"MISSING ARTIFACT: {test_log_path} (Required to prove TDD Hard Gate)")
    else:
        with open(test_log_path, 'r') as f:
            content = f.read()
            # Look for common failure indicators in tracebacks
            failure_patterns = [
                r"AssertionError",
                r"FAILED",
                r"E       ", # pytest error indicator
                r"Traceback",
                r"Exception:",
                r"Error:"
            ]
            if not any(re.search(p, content, re.IGNORECASE) for p in failure_patterns):
                errors.append(f"INVALID ARTIFACT: {test_log_path} does not contain a verifiable failure trace. You must run the tests and capture the failure before implementation.")
            else:
                print(f"PASS: Found verifiable failure in {test_log_path}")

    if errors:
        print("\n--- GATEKEEPER FAILURE ---")
        for err in errors:
            print(f"- {err}")
        print("\nACTION: You MUST instruct the sub-agent to produce the missing or corrected artifacts before proceeding.")
        sys.exit(1)

    print("\nSUCCESS: Phase 4 Hard Gate passed. Implementation is authorized.")
    sys.exit(0)

def check_phase_5_ready(workspace_path):
    """Verifies that Phase 5 (Wrap-up) is authorized via Review and QA reports."""
    review_path = os.path.join(workspace_path, "artifacts", "code_review_report.md")
    qa_path = os.path.join(workspace_path, "artifacts", "qa_report.md")
    
    errors = []
    if not os.path.exists(review_path):
        errors.append(f"MISSING ARTIFACT: {review_path}")
    if not os.path.exists(qa_path):
        errors.append(f"MISSING ARTIFACT: {qa_path}")
        
    if errors:
        print("\n--- GATEKEEPER FAILURE ---")
        for err in errors:
            print(f"- {err}")
        sys.exit(1)
        
    print("PASS: Review and QA reports found. PR authorized.")
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Harness Protocol Gatekeeper")
    parser.add_argument("--phase", type=int, choices=[1, 3, 4, 5], required=True, help="The phase to authorize")
    parser.add_argument("--workspace", type=str, default=".", help="Path to the workspace root")
    
    args = parser.parse_args()
    
    if args.phase == 1:
        check_phase_1_ready(args.workspace)
    elif args.phase == 3:
        check_phase_3_ready(args.workspace)
    elif args.phase == 4:
        check_phase_4_ready(args.workspace)
    elif args.phase == 5:
        check_phase_5_ready(args.workspace)

if __name__ == "__main__":
    main()
