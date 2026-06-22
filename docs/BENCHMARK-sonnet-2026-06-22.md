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

## Implications for harness design

The TDD mandate is appropriate for **greenfield development** where the agent defines the acceptance criteria. It is harmful for **open-ended debugging in unfamiliar codebases** where a hidden oracle defines the acceptance criteria and the agent cannot know what edge cases it checks.

The "combine turns" instruction compounds this by reducing the iterative verification that might otherwise surface the discrepancy.

**Candidate mitigations:**

1. **Task-conditional TDD**: disable the TDD lifecycle rule in debugging/bug-fix task contexts; keep it for implementation tasks where the agent owns the spec.
2. **Uncap turns for debugging**: remove or relax the "combine turns" directive when harness is used in benchmark mode.
3. **Simpler remediation heuristics**: for handler/sink cleanup in particular, "remove all and start fresh" is more correct than path-matching for benchmark tasks.

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

---

## Next steps

1. **Run Haiku** — second model data point, cheap. If the pattern holds (harness ≤ baseline), the TDD false-confidence mechanism is model-agnostic.
2. **Inspect langflow-high and bat-low** — both follow baseline-wins pattern; check whether TDD false confidence is the mechanism there too, or whether a different failure mode applies.
3. **Design a debugging-safe harness variant** — strip TDD lifecycle mandate, relax "combine turns," test on harness-bench. Measure whether accuracy improves toward or past baseline.
4. **ECC investigation** — ECC matched baseline (48 % vs 50 %) without the TDD mandate. Understanding what ECC injects vs what `claude-harness` injects isolates the causal variable.
