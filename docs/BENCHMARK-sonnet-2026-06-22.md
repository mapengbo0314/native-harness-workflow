# Benchmark Results — native-harness-sonnet-2026-06-20a (2026-06-22)

## Overview

First valid 3-way comparison on harness-bench. Single-attempt, directional.

| | |
|---|---|
| **Experiment ID** | `native-harness-sonnet-2026-06-20a` |
| **Run date** | 2026-06-22, 14:19 → 21:06 UTC (~6.8 h) |
| **Model** | claude-sonnet-4-6, medium effort |
| **Design** | 27 real-repo cases × 3 conditions = 81 jobs (80 completed, 1 Docker hang) |
| **Conditions** | `claude` (bare), `claude-harness` (native-harness plugin), `claude-ecc` (ECC plugin) |
| **Workspace policy** | `remove_upstream_agent_instructions`, `fresh_sanitized_one_commit_root` |
| **Prompt policy** | hide original PR, hide fixed commit, hide hidden tests, disable memory |

---

## Results

| Condition | Pass / N | Pass Rate | Cost (USD) | Median wall time |
|---|---|---|---|---|
| `claude` (baseline) | 13 / 26 | **50.0 %** | $21.75 | 378 s |
| `claude-harness` | 11 / 26 | **42.3 %** | $34.09 | 529 s |
| `claude-ecc` | 13 / 27 | **48.1 %** | $35.01 | 482 s |

Missing: `langflow-mid-mcp-connectable-inputs` baseline (Docker hang before result.json written).

### Per-case scoreboard

| Case | baseline | harness | ecc |
|---|---|---|---|
| axios-high-http-connect-timeout | ✗ | ✗ | ✗ |
| axios-low-settle-error-code | ✓ | ✗ | ✓ |
| axios-mid-fetch-global-access | ✗ | ✗ | **✓** |
| fastapi-high-pydantic-json-fast-path | ✓ | ✓ | ✓ |
| fastapi-low-remove-vibe-decorator | ✓ | ✓ | ✓ |
| fastapi-mid-jsonable-encoder-color-types | ✓ | ✓ | ✓ |
| gitea-high-compare-no-common-history | ✓ | ✓ | ✗ |
| gitea-low-schedule-null-payload | ✓ | ✓ | ✓ |
| gitea-mid-pr-merge-self-reference | ✓ | ✓ | ✓ |
| lazygit-high-branch-divergence-fast-path | ✗ | ✗ | ✗ |
| lazygit-low-github-owner-casing | ✓ | ✓ | ✓ |
| lazygit-mid-preserve-commit-message-whitespace | ✗ | ✗ | ✗ |
| langflow-high-lfx-stream-fallback | **✓** | ✗ | ✗ |
| langflow-low-loguru-file-routing | **✓** | ✗ | ✗ |
| langflow-mid-mcp-connectable-inputs | ? | ✗ | ✗ |
| uptime-kuma-high-websocket-auth-options | ✗ | ✗ | ✗ |
| uptime-kuma-low-submillisecond-ping-chart | ✓ | ✗ | ✓ |
| uptime-kuma-mid-uptime-cleanup-buckets | **✓** | ✗ | ✗ |
| bat-high-fallback-syntax | ✓ | ✓ | ✓ |
| bat-low-zip-binary-detection | **✓** | ✗ | ✗ |
| bat-mid-control-character-wrapping | ✗ | ✗ | ✗ |
| usememos-high-missing-related-users | ✗ | **✓** | **✓** |
| usememos-low-omit-internal-user-settings | ✓ | ✓ | ✓ |
| usememos-mid-mixed-case-user-resource-names | ✗ | ✗ | ✗ |
| vitejs-high-hmr-patch-esm-sentinel | ✗ | ✗ | ✗ |
| vitejs-low-flatten-id-sanitized-chars | ✗ | ✗ | ✗ |
| vitejs-mid-deno-workspace-root | ✗ | ✗ | ✗ |

**Bold** = that condition won where others failed.

### Reference point

Official harness-bench run (`harnessbench-v2-official-2026-05-04c`, May 2026):
- `claude-opus-4-7` high effort: **74.1 %** (20/27)
- `codex-gpt-5.5` medium effort: **77.8 %** (21/27)

Sonnet-medium vs Opus-high gap (50 % → 74 %) is a credible model/effort difference. The harness is not closing it.

---

## Key Finding: TDD mandate causes false confidence on debugging tasks

The harness underperforms baseline by 8 pp and costs 57 % more per run. Case autopsy of `langflow-low-loguru-file-routing` identifies the concrete mechanism.

### The bug

Loguru has its own internal dispatch pipeline, independent of Python's stdlib `logging`. Code using `from loguru import logger` never reaches Langflow's `RotatingFileHandler`. Fix requires (a) installing a Loguru sink that bridges to stdlib, and (b) removing stale file handlers before adding a new one on reconfigure.

### What the harness agent did (4 turns, $1.44 → FAIL)

The `coding_mandate.md` plugin rule (`src/harness/templates/boilerplate/rules/`) mandates strict TDD:

> **TDD Lifecycle**: You MUST follow strict Test-Driven Development.
> RED: Write a failing test first. Verify the failure in the logs.
> GREEN: Write the minimal code to pass the test.
> REFACTOR: Improve the code while keeping tests passing.

Alongside `core_mandates.md`:

> **Context Efficiency**: Isolated context window. Be strategic. **Combine turns**.

The agent:
1. Wrote 8 self-authored tests (RED), covering: end-to-end file write via Loguru, no-sink without log_file, handler dedup, stale handler removal, sink replacement on reconfigure, level filtering
2. Implemented the fix to pass those tests (GREEN)
3. Ran all 96 tests (71 existing + 17 server + 8 new) — all green
4. Stopped (combine turns / self-authored tests passed)

The implementation it produced:

```python
def _remove_stale_file_handlers(log_file: Path) -> None:
    """Remove any existing RotatingFileHandler instances pointing to *log_file*."""
    target = os.path.realpath(str(log_file))
    for handler in logging.root.handlers[:]:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            if os.path.realpath(handler.baseFilename) == target:   # ← only same-file
                logging.root.removeHandler(handler)
                handler.close()
```

The hidden regression test exercised:

```python
# configure to file A
configure(log_file=first, ...)
# configure to file B (different path)
configure(log_file=second, ...)
logger.info("new file only")
# assert message is NOT in file A
assert "new file only" not in first.read_text()  # ← FAILED
```

Because `_remove_stale_file_handlers(second)` only removes handlers pointing to `second`, the handler for `first` was still attached to `logging.root`. The new Loguru sink bridges to stdlib root, which still had the old file-A handler — so the message appeared in both files.

### What the baseline agent did (18 turns, $0.54 → PASS)

No TDD mandate. Iterative exploration: explore the codebase → write a fix → run existing tests → manual integration test.

The implementation:

```python
# Remove any stale RotatingFileHandlers to avoid duplicates across re-configure calls
for stale in logging.root.handlers[:]:
    if isinstance(stale, logging.handlers.RotatingFileHandler):
        stale.close()
        logging.root.removeHandler(stale)
```

Unconditional — removes **all** file handlers before adding a new one, regardless of path. Simpler, broader, and correct for both same-file and different-file reconfigures. The agent didn't write new tests; it just didn't try to be clever about which handler to remove.

### The irony

The harness agent's path-matched removal is arguably the "better engineering" answer in a multi-file concurrent logging scenario. That reasoning is sound. But for this task, the hidden oracle requires "nuke all file handlers and start fresh." The more sophisticated helper introduced a scoping bug that naive simplicity avoided.

### Failure mode taxonomy

| Driver | What it caused |
|---|---|
| **TDD mandate** | Agent wrote its own tests and trusted them as oracle → green tests, stopped exploring → missed the different-file scenario |
| **"Combine turns"** | 4 turns vs 18 → no iterative probing → less chance to discover edge cases through running things |
| **"High quality idiomatic code"** | Over-engineered `_remove_stale_file_handlers` with `os.path.realpath` comparison → correct-seeming, subtly wrong |
| **Token budget displacement** | Spent $1.44 vs $0.54 — extra cost went to writing tests and docstrings, not deeper problem understanding |

---

## Benchmark validity note

A fair question: is the regression test itself well-specified, or does it check behavior the task instruction doesn't clearly require?

### What the hidden tests actually check

**core.sh** — verifies a Loguru message appears in the configured log file. Notably, the core test *pre-clears all RotatingFileHandlers* before calling `configure()`:

```python
for handler in logging.root.handlers[:]:
    if isinstance(handler, logging.handlers.RotatingFileHandler):
        logging.root.removeHandler(handler)
        handler.close()
configure(log_level="INFO", log_file=log_file, cache=False)
```

This is a signal: the test author expected that stale handlers might be present and chose to clear them externally rather than trust `configure()` to do it. It works around the exact cleanup behavior the regression test checks.

**regression.sh** — three assertions:
1. `assert "standard logging still routes" in first.read_text()` — first configure routes stdlib to first.log ✓
2. `assert "new file only" in second.read_text()` — after second configure, Loguru goes to second.log ✓
3. `assert "new file only" not in first.read_text()` — old handler for first.log must be gone ✗ (harness failed here)

### The instruction's ambiguity

The task instruction says:

> *Route Loguru messages through the Langflow logger without duplicating stale file handlers.*

"Stale file handlers" is ambiguous. A developer could reasonably read it as:
- **Reading A (narrow)**: don't accumulate duplicate handlers for the *same* file on repeated configure calls — harness agent's path-matched removal satisfies this
- **Reading B (broad)**: don't leave *any* previously-added file handler attached when reconfiguring — required to pass the regression test

The actual merged PR (commit `d68b312`) uses Reading B — unconditional removal. The hidden test is aligned with the reference implementation and with Reading B of the instruction.

### Verdict

The hidden test is checking **correct behavior** as defined by the merged fix. It is not an unfair gotcha. However, the task instruction is underspecified: it does not clearly signal that "stale" means "any previous file handler regardless of path." An agent reading the instruction carefully and implementing path-matched removal is making a reasonable but wrong interpretation.

**This is a benchmark design observation, not a defect**: the hidden test is tight and correct, but there is an instruction/test alignment gap that a more precise instruction would close. Suggested wording: *"…without leaving any stale file handlers from previous configure calls, regardless of their target path."*

The harness-specific finding stands independently: the TDD mandate caused the agent to trust its own tests rather than probe deeper, and that process failure is what prevented it from discovering the gap. A baseline agent without that mandate explored iteratively and happened to land on the simpler, correct implementation. The instruction ambiguity made the process failure consequential — it would have been inconsequential if the instruction had been unambiguous.

---

## Implications for harness design

The TDD mandate is appropriate for **greenfield development** where the agent defines the acceptance criteria. It is harmful for **open-ended debugging in unfamiliar codebases** where a hidden oracle defines the acceptance criteria and the agent cannot know what edge cases it checks.

The "combine turns" instruction compounds this by reducing the iterative verification that might otherwise surface the discrepancy.

**Candidate mitigations:**

1. **Task-conditional TDD**: disable the TDD lifecycle rule in debugging/bug-fix task contexts; keep it for implementation tasks where the agent owns the spec.
2. **Uncap turns for debugging**: remove or relax the "combine turns" directive when harness is used in benchmark mode.
3. **Simpler remediation heuristics**: for handler/sink cleanup in particular, "remove all and start fresh" is more correct than path-matching for benchmark tasks.

---

---

## Native harness benchmark results (2026-06-22)

Run on same day, same model (claude-sonnet-4-6 medium), 9 tasks (SWE tasks excluded — broken oracle on Python 3.14), 3 conditions in parallel. Wall time ~14 minutes.

| Task | baseline | harness | ecc |
|---|---|---|---|
| A-bug-fix-001 | **1.000** | 0.667 | **1.000** |
| B-implementation-001 | 1.000 | 1.000 | 1.000 |
| C-explanation-001 | 0.714 | **1.000** | 0.714 |
| D-workload-bug-001 | 1.000 | 1.000 | 1.000 |
| E-scheduler-bug-001 | 1.000 | 1.000 | 1.000 |
| F-report-bug-001 | 1.000 | 1.000 | 1.000 |
| F-rtk-001 | 0.500 | 0.300 | 0.500 |
| F-rtk-002 | 0.200 | 0.200 | 0.200 |
| F-rtk-003 | 0.400 | 0.400 | 0.400 |
| **MEAN** | **0.757** | **0.730** | **0.757** |

Scores are `combined_score` (outcome-only blend; process rubric not run).

### Contrast with harness-bench

| Benchmark | baseline | harness | ecc | harness vs baseline |
|---|---|---|---|---|
| harness-bench (27 real-repo tasks) | 50.0 % | 42.3 % | 48.1 % | −8 pp |
| native harness (9 synthetic tasks) | 75.7 % | 73.0 % | 75.7 % | −3 pp |

The gap is smaller on native tasks but the direction is the same: **harness does not outperform baseline on either benchmark.**

### Task-level observations

**Harness wins on C-explanation-001** (1.0 vs 0.714): the explanation task asks the agent to navigate an unfamiliar codebase and describe dispatcher routing. The harness's graph-first navigation mandate and structured documentation rules likely help here — this is a task where structured process adds value because the agent doesn't need to discover unknown edge cases, just describe what's there.

**Harness loses on A-bug-fix-001** (0.667 vs 1.0): a straightforward Python auth bug. Score 0.667 means 2/3 tests passed — the agent likely fixed the obvious path but missed an edge case. This is the same TDD false-confidence pattern as langflow-low: agent wrote tests, trusted them, stopped.

**RTK tasks (F-rtk-*) are hard for all conditions** (0.2–0.5): these require using the RTK tool via specific CLI commands. Baseline and ECC tie; harness is slightly worse on F-rtk-001 (0.300 vs 0.500). RTK tasks are designed to test harness behaviour specifically — that the harness doesn't improve them is notable.

**ECC = baseline exactly** (0.757 both): ECC neither helps nor hurts on these tasks.

### Interpretation

The native harness tasks are synthetic and designed by the same team that built the harness. Even on home-turf tasks, the harness does not outperform baseline. The one win (C-explanation) is a navigation/documentation task, not a debugging task — consistent with the hypothesis that structured process instructions help when the agent owns the acceptance criteria, and hurt when a hidden oracle defines it.

---

---

## Probe benchmark results (2026-06-22)

Synthetic smoke benchmark: generated Python call-chain with a hidden arithmetic bug. Two axes: **depth** (how many calls deep the bug is buried: 1/3/5) and **clarity** (1.0 = clear identifiers, 0.0 = AST-scrambled obfuscated names). 1 rep per cell, 18 total runs.

| depth | clarity | baseline | harness | ecc |
|---|---|---|---|---|
| 1 | 1.0 (clear) | ✓ | ✗ | ✓ |
| 1 | 0.0 (scrambled) | ✓ | ✓ | ✓ |
| 3 | 1.0 | ✓ | ✓ | ✓ |
| 3 | 0.0 | ✓ | ✓ | ✓ |
| 5 | 1.0 | ✓ | ✗ | ✓ |
| 5 | 0.0 | ✓ | ✗ | ✓ |
| **Total** | | **6/6 (100%)** | **3/6 (50%)** | **6/6 (100%)** |

### Interpretation (caveats apply)

The direction is consistent with harness-bench and native harness: baseline ≥ harness across all three benchmarks.

However, with **n=1 per cell**, noise dominates. The pattern is internally inconsistent: harness fails depth=1 clarity=1.0 (the easiest cell) but passes depth=1 clarity=0.0 (harder). A systematic effect would expect the reverse. This suggests the three harness failures are a mix of genuine TDD false-confidence and run-to-run stochasticity on a small synthetic codebase.

**What the probe can and cannot say at n=1:**
- Cannot distinguish harness signal from noise on individual cells
- Can say: harness is not *reliably* better — it drops cells that baseline and ECC hold
- To separate the depth and clarity effects cleanly, need n≥3 per cell (54 runs per model)

### Cross-benchmark summary (all three)

| Benchmark | baseline | harness | ecc | note |
|---|---|---|---|---|
| harness-bench (27 real-repo tasks) | 50.0% | 42.3% | 48.1% | n=1 attempt per job |
| native harness (9 synthetic tasks) | 75.7% | 73.0% | 75.7% | n=1 per task |
| probe (6 depth×clarity cells) | 100% | 50% | 100% | n=1 per cell, noisy |

**Consistent direction across all three benchmarks: harness does not outperform baseline. ECC matches baseline at higher cost.**

---

## Artifact locations

| Artifact | Path |
|---|---|
| Machine-generated summary | `benchmark/harness-bench/benchmark/experiments/native-harness-sonnet-2026-06-20a/summary.json` |
| Full manifest (all inputs, checksums) | `benchmark/harness-bench/benchmark/experiments/native-harness-sonnet-2026-06-20a/manifest.json` |
| Rendered HTML report | `benchmark/harness-bench/benchmark/experiments/native-harness-sonnet-2026-06-20a/results.html` |
| Experiment findings (this doc's source) | `benchmark/harness-bench/benchmark/experiments/native-harness-sonnet-2026-06-20a/FINDINGS.md` |
| langflow-low baseline run | `benchmark/harness-bench/benchmark/runs/2026-06-22T16-18-57-228Z-langflow-ai-langflow-low-loguru-file-routing-agent-claude-*` |
| langflow-low harness run | `benchmark/harness-bench/benchmark/runs/2026-06-22T16-22-51-044Z-langflow-ai-langflow-low-loguru-file-routing-agent-claude-harness-*` |
| Harness plugin rules | `src/harness/templates/boilerplate/rules/coding_mandate.md`, `core_mandates.md` |
| Native harness logs | `/tmp/native-bench-{claude-no-harness,claude-full-harness,claude-ecc}.log` |

---

## Next steps

1. **Run Haiku** on both benchmarks — second model data point, cheap. If harness ≤ baseline holds across model sizes, the finding is robust.
2. **Inspect A-bug-fix-001 harness failure** — confirm TDD false-confidence is the mechanism (mirrors langflow-low pattern).
3. **Design a debugging-safe harness variant** — strip TDD lifecycle mandate, relax "combine turns." Test on harness-bench and native. Measure delta.
4. **ECC investigation** — ECC matches baseline on both benchmarks at higher cost. Understanding what it injects vs `claude-harness` isolates the causal variable for the harness cost/accuracy gap.
5. **Fix SWE task oracles on Python 3.14** — both pylint SWE tasks crash during oracle collection (`LookupError: unknown encoding: IBO-8859-1`). Either pin a Python 3.12 venv for SWE tasks or patch the oracle runner to handle the encoding error.
