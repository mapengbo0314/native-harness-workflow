#!/usr/bin/env python3
"""
Deterministic benchmark result summariser.

Usage:
    python3 benchmark/analysis/summarise.py
    python3 benchmark/analysis/summarise.py --model haiku
    python3 benchmark/analysis/summarise.py --model sonnet
    python3 benchmark/analysis/summarise.py --model haiku --model sonnet
"""
from __future__ import annotations

import argparse
import glob
import json
import random
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
RUNS_GLOB = str(REPO_ROOT / "benchmark/harness-bench/benchmark/runs/*/result.json")

COND_ORDER = ["claude", "claude-harness", "claude-ecc"]
COND_LABEL = {"claude": "baseline", "claude-harness": "harness", "claude-ecc": "ecc"}

BOOTSTRAP_N = 10_000
BOOTSTRAP_SEED = 42


def load_results(model_filter: list[str]) -> dict:
    """Load best attempt per (model, condition, case_id). Returns nested dict."""
    best: dict[tuple, dict] = {}
    for path in sorted(glob.glob(RUNS_GLOB)):
        d = json.load(open(path))
        model = d.get("model", "")
        if model_filter and not any(f in (model or "") for f in model_filter):
            continue
        key = (model, (d.get("condition_id") or "").split(":")[0], d.get("case_id") or "")
        tr = d.get("test_result") or {}
        passed = bool(tr.get("success"))
        prev = best.get(key)
        if prev is None or (passed and not prev["passed"]):
            best[key] = {
                "passed": passed,
                "repo": d.get("repo", ""),
                "difficulty": (d.get("case_metadata") or {}).get("difficulty", "?"),
                "duration_ms": d.get("duration_ms", 0),
                "model": model,
                "cond": key[1],
                "case_id": key[2],
            }
    return best


def pass_rate(items: list[bool]) -> float:
    return sum(items) / len(items) if items else 0.0


def bootstrap_ci(cases: list[str], results_by_case: dict[str, bool], seed: int = BOOTSTRAP_SEED, n: int = BOOTSTRAP_N) -> tuple[float, float]:
    rng = random.Random(seed)
    deltas = []
    for _ in range(n):
        sample = rng.choices(cases, k=len(cases))
        deltas.append(sum(results_by_case[c] for c in sample) / len(sample))
    deltas.sort()
    return deltas[int(n * 0.025)], deltas[int(n * 0.975)]


def print_header(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def print_section(text: str) -> None:
    print(f"\n--- {text} ---")


def run(model_filter: list[str]) -> None:
    best = load_results(model_filter)

    # Group by model
    by_model: dict[str, dict] = defaultdict(lambda: defaultdict(dict))
    for (model, cond, case_id), row in best.items():
        if model and cond and case_id:
            by_model[model][cond][case_id] = row

    for model, by_cond in sorted(by_model.items()):
        total_cases = sum(len(v) for v in by_cond.values())
        if total_cases < 9:
            continue  # skip models with too few results (old/other experiments)
        print_header(f"Model: {model}")

        # --- Overall pass rates ---
        print_section("Overall pass rate")
        all_cases = sorted({c for cond_data in by_cond.values() for c in cond_data})
        print(f"  Cases with results: {len(all_cases)}")
        rates = {}
        for cond in COND_ORDER:
            cond_data = by_cond.get(cond, {})
            n = len(cond_data)
            if n == 0:
                continue
            passed = sum(1 for r in cond_data.values() if r["passed"])
            rates[cond] = passed / n
            print(f"  {COND_LABEL[cond]:10s}: {passed:2d}/{n:2d} = {100*rates[cond]:.1f}%")

        if "claude" in rates:
            print()
            for cond in ["claude-harness", "claude-ecc"]:
                if cond in rates:
                    delta = (rates[cond] - rates["claude"]) * 100
                    print(f"  {COND_LABEL[cond]} vs baseline: {delta:+.1f} pp")

        # --- Per-difficulty ---
        print_section("By difficulty")
        for diff in ["low", "mid", "high"]:
            row_parts = []
            for cond in COND_ORDER:
                cond_data = by_cond.get(cond, {})
                items = [r["passed"] for r in cond_data.values() if r["difficulty"] == diff]
                if items:
                    row_parts.append(f"{COND_LABEL[cond]}: {sum(items)}/{len(items)}")
            if row_parts:
                print(f"  {diff:4s}  " + "   ".join(row_parts))

        # --- Per-repo ---
        print_section("By repo")
        repos = sorted({r["repo"] for cond_data in by_cond.values() for r in cond_data.values()})
        for repo in repos:
            row_parts = []
            for cond in COND_ORDER:
                cond_data = by_cond.get(cond, {})
                items = [r["passed"] for r in cond_data.values() if r["repo"] == repo]
                if items:
                    row_parts.append(f"{COND_LABEL[cond]}: {'✓' if all(items) else '✗' if not any(items) else f'{sum(items)}/{len(items)}'}")
            if row_parts:
                print(f"  {repo:30s}  " + "   ".join(row_parts))

        # --- Case-level: who wins each case ---
        print_section("Per-case winner (baseline vs harness)")
        baseline = by_cond.get("claude", {})
        harness = by_cond.get("claude-harness", {})
        shared_cases = sorted(set(baseline) & set(harness))
        harness_only_wins = []
        baseline_only_wins = []
        both_pass = []
        both_fail = []
        for c in shared_cases:
            b = baseline[c]["passed"]
            h = harness[c]["passed"]
            if b and h:
                both_pass.append(c)
            elif not b and not h:
                both_fail.append(c)
            elif h and not b:
                harness_only_wins.append(c)
            elif b and not h:
                baseline_only_wins.append(c)

        print(f"  Both pass:          {len(both_pass):2d}  {[c.split('-',2)[2] for c in both_pass][:4]}")
        print(f"  Both fail:          {len(both_fail):2d}")
        print(f"  Harness only wins:  {len(harness_only_wins):2d}  {[c.split('-',2)[2] for c in harness_only_wins]}")
        print(f"  Baseline only wins: {len(baseline_only_wins):2d}  {[c.split('-',2)[2] for c in baseline_only_wins]}")

        # --- Bootstrap CI on harness delta ---
        if shared_cases:
            print_section("Bootstrap 95% CI on harness delta vs baseline (n=10k, seed=42)")
            baseline_results = {c: baseline[c]["passed"] for c in shared_cases}
            harness_results = {c: harness[c]["passed"] for c in shared_cases}

            # Resample pairs, compute delta each time
            rng = random.Random(BOOTSTRAP_SEED)
            deltas = []
            for _ in range(BOOTSTRAP_N):
                sample = rng.choices(shared_cases, k=len(shared_cases))
                b_rate = sum(baseline_results[c] for c in sample) / len(sample)
                h_rate = sum(harness_results[c] for c in sample) / len(sample)
                deltas.append(h_rate - b_rate)
            deltas.sort()
            lo, hi = deltas[int(BOOTSTRAP_N * 0.025)], deltas[int(BOOTSTRAP_N * 0.975)]
            observed = pass_rate(list(harness_results.values())) - pass_rate(list(baseline_results.values()))
            print(f"  Observed delta: {observed:+.1%}")
            print(f"  95% CI:         [{lo:+.1%}, {hi:+.1%}]")
            sig = "CI excludes 0 → significant" if lo > 0 or hi < 0 else "CI includes 0 → not significant"
            print(f"  Verdict:        {sig}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", default=[], help="Filter by model substring (e.g. haiku, sonnet). Repeatable.")
    args = parser.parse_args()
    run(args.model)


if __name__ == "__main__":
    main()
