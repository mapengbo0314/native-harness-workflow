# Probe Benchmark

Synthetic benchmark for testing whether an agent can trace a generated Python
call chain, find the terminal arithmetic defect, and repair it.

This is a probe benchmark, not a production-quality harness score.

## What It Measures

The probe varies two axes:

| Axis | Meaning |
|---|---|
| `depth` | Number of forwarding modules between `src.pipeline.run_pipeline` and the defective leaf function. |
| `clarity` | Fraction of generated symbols left semantically readable. `1.0` is clear names, `0.0` is fully scrambled symbols and filenames. |

The generated task is intentionally small:

1. Create a temporary Python workspace.
2. Generate a linear module chain.
3. Put a failing arithmetic operation at the leaf.
4. Optionally scramble symbols with an AST-based renamer.
5. Ask the agent to make `pytest tests/ -v` pass.

The oracle is binary: the pytest suite passes or it does not.

## How To Run

Dry run, which verifies adapter setup only:

```bash
python3 benchmark/probe/run_probe.py \
  --models codex-no-harness,codex-full-harness \
  --depths 1 \
  --clarities 1.0,0.5 \
  --reps 1 \
  --mode dry
```

Live Codex smoke run:

```bash
python3 benchmark/probe/run_probe.py \
  --models codex-no-harness,codex-full-harness \
  --depths 1,2,4 \
  --clarities 0.5 \
  --reps 1 \
  --mode live
```

Harsher Codex run used on 2026-06-17:

```bash
python3 benchmark/probe/run_probe.py \
  --models codex-no-harness,codex-full-harness \
  --depths 7,9 \
  --clarities 0.25,0.0 \
  --reps 1 \
  --mode live
```

## 2026-06-17 Codex Results

Codex passed every generated probe attempted.

| Model | Depth | Clarity | Pass | Tokens |
|---|---:|---:|---:|---:|
| `codex-no-harness` | 1 | 0.5 | 1/1 | 119,851 |
| `codex-no-harness` | 2 | 0.5 | 1/1 | 120,135 |
| `codex-no-harness` | 4 | 0.5 | 1/1 | 123,217 |
| `codex-no-harness` | 7 | 0.25 | 1/1 | 127,489 |
| `codex-no-harness` | 7 | 0.0 | 1/1 | 100,314 |
| `codex-no-harness` | 9 | 0.25 | 1/1 | 166,344 |
| `codex-no-harness` | 9 | 0.0 | 1/1 | 123,723 |
| `codex-full-harness` | 1 | 0.5 | 1/1 | 333,897 |
| `codex-full-harness` | 2 | 0.5 | 1/1 | 649,815 |
| `codex-full-harness` | 4 | 0.5 | 1/1 | 432,361 |
| `codex-full-harness` | 7 | 0.25 | 1/1 | 431,553 |
| `codex-full-harness` | 7 | 0.0 | 1/1 | 305,525 |
| `codex-full-harness` | 9 | 0.25 | 1/1 | 442,647 |
| `codex-full-harness` | 9 | 0.0 | 1/1 | 444,122 |

Observed latency ranges:

| Model | Range |
|---|---:|
| `codex-no-harness` | 28.8s to 49.8s |
| `codex-full-harness` | 76.3s to 143.0s |

## Interpretation

Keep this benchmark, but keep it in the right role.

It is useful as a cheap smoke test for:

- adapter wiring,
- generated workspace validity,
- basic agent ability to repair a synthetic defect,
- rough token and latency overhead of harness context.

It is not currently useful as a harness-quality metric, because Codex solves all
tested variants. The benchmark does not yet produce a capability separation
between `codex-no-harness` and `codex-full-harness`; it mostly measures overhead.

The consistent signal from the 2026-06-17 Codex runs is overhead:

- full harness used roughly 2.7x to 3.6x more tokens on the harsher cases,
- full harness took roughly 2.4x to 3.6x longer on the harsher cases,
- no success-rate gain was measurable because both configurations passed.

## Recommendation

Keep the probe as a smoke benchmark, not as a headline benchmark.

Do not use it to claim that the harness improves or worsens agent capability
until the generator includes failure modes that baseline Codex sometimes misses.

Good next variants:

- branching call graphs instead of a single linear chain,
- multiple plausible arithmetic defects with one true root cause,
- misleading nearby tests or helper functions,
- data-dependent failures instead of a direct constant mismatch,
- tasks requiring a small new regression test before fixing,
- distractor modules that compile and look relevant but are not on the failing path.

The useful future metric is:

```text
value = success_rate_delta / token_cost_multiplier
```

Until baseline failure appears, `success_rate_delta` is zero and the probe is
only measuring overhead.
