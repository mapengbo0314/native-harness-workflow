"""Routing accuracy benchmark — tests the classifier directly without spawning Claude sessions.

Tests two classifiers:
  - fallback_classify: deterministic keyword-based (from boilerplate hooks)
  - llm_classify: LLM-based via the dispatcher (requires Claude CLI)

Usage:
    python benchmark/routing/run_routing.py
    python benchmark/routing/run_routing.py --classifier fallback
    python benchmark/routing/run_routing.py --classifier llm
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

CASES_PATH = Path(__file__).parent / "test_cases.yaml"
BOILERPLATE_HOOK = (
    Path(__file__).parent.parent.parent
    / "src/harness/templates/boilerplate/hooks/prompt_classifier.py"
)


def load_fallback_classify():
    """Extract fallback_classify by reading and exec-ing only that function."""
    source = BOILERPLATE_HOOK.read_text()
    # Extract just the function definition without executing module-level side effects
    start = source.find("def fallback_classify(")
    end = source.find("\n@", start)  # next decorator ends the function
    fn_source = source[start:end].strip()
    ns: dict = {}
    exec(fn_source, ns)
    return ns["fallback_classify"]


def llm_classify(prompt: str) -> str:
    """Use Claude CLI to classify a prompt the same way the dispatcher would."""
    system = (
        "You are a routing classifier. Classify the user prompt into exactly one category:\n"
        "A = bug fix or diagnosis (errors, crashes, broken things)\n"
        "B = implementation or new feature\n"
        "C = explanation, navigation, or 'how does X work'\n"
        "E = miscellaneous or off-topic\n\n"
        "Reply with a single letter: A, B, C, or E. Nothing else."
    )
    result = subprocess.run(
        ["claude", "--print", "--dangerously-skip-permissions",
         "--append-system-prompt", system],
        input=prompt, capture_output=True, text=True, timeout=30,
    )
    letter = result.stdout.strip()[:1].upper()
    return letter if letter in "ABCE" else "E"


def run(classifier_name: str) -> None:
    cases = yaml.safe_load(CASES_PATH.read_text())["cases"]

    if classifier_name == "fallback":
        classify = load_fallback_classify()
    else:
        classify = llm_classify

    results = []
    correct = 0
    by_category: dict[str, dict] = {}

    for case in cases:
        prompt = case["prompt"]
        expected = case["expected"]
        actual = classify(prompt)
        passed = actual == expected
        if passed:
            correct += 1
        results.append({"prompt": prompt, "expected": expected, "actual": actual, "passed": passed})

        cat = by_category.setdefault(expected, {"correct": 0, "total": 0})
        cat["total"] += 1
        if passed:
            cat["correct"] += 1

    total = len(cases)
    accuracy = correct / total

    print(f"\n{'='*50}")
    print(f"Classifier: {classifier_name}   Accuracy: {accuracy:.0%} ({correct}/{total})")
    print(f"{'='*50}")

    print(f"\n{'Category':<6} {'Correct':>8} {'Total':>8} {'Accuracy':>10}")
    print("-" * 36)
    for cat in sorted(by_category):
        d = by_category[cat]
        cat_acc = d["correct"] / d["total"]
        print(f"{cat:<6} {d['correct']:>8} {d['total']:>8} {cat_acc:>10.0%}")

    print(f"\nFailed cases:")
    for r in results:
        if not r["passed"]:
            print(f"  [{r['expected']}→{r['actual']}] {r['prompt']!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--classifier", choices=["fallback", "llm", "both"], default="both")
    args = parser.parse_args()

    classifiers = ["fallback", "llm"] if args.classifier == "both" else [args.classifier]
    for c in classifiers:
        run(c)


if __name__ == "__main__":
    main()
