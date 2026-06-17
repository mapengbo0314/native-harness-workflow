# Harness Benchmark

Compares harness performance across configurations using either Claude Code or
Codex CLI. The benchmark is built on top of
[harness-bench](https://github.com/Qihoo360/harness-bench) (clawbench_v2),
copied into `benchmark/clawbench_v2/`, extended with our own adapters.

## Harness configurations

| Config | What it is |
|---|---|
| `no_harness` | Raw agent, no harness context |
| `minimal` | `CLAUDE.md` + `AGENTS.md` only |
| `full_harness` | Full plugin (`harness-wf-plugin`) installed |
| `rtk` | RTK hook + RTK system prompt |
| `full_harness_rtk` | Full plugin + RTK hook + RTK system prompt |

## Quick start

```bash
# List available tasks
python benchmark/run.py tasks

# Run a single task with one model
python benchmark/run.py run-task --task A-bug-fix-001 --model claude-no-harness --mode live

# Run all tasks with a model
python benchmark/run.py run-suite --model claude-full-harness --mode live

# Delete the sandbox when done (otherwise it is kept in /tmp/harness-bench-work/)
python benchmark/run.py run-task --task A-bug-fix-001 --model claude-no-harness --mode live --delete-sandbox
```

## Models

Defined in `benchmark/config/models.yaml`:

| Model ID | Adapter | Harness config | Notes |
|---|---|---|---|
| `claude-no-harness` | claude_code | no_harness | Sonnet baseline |
| `claude-full-harness` | claude_code | full_harness | Sonnet + full plugin |
| `claude-full-harness-rtk` | claude_code | full_harness_rtk | Sonnet + full plugin + RTK |
| `claude-haiku-no-harness` | claude_code | no_harness | Haiku baseline (cheap) |
| `claude-haiku-full-harness` | claude_code | full_harness | Haiku + full plugin (cheap) |
| `claude-ecc` | claude_code | ecc | ECC plugin (`benchmark/.cache/ecc`) |
| `codex-no-harness` | codex | no_harness | Codex baseline |
| `codex-full-harness` | codex | full_harness | Codex + full plugin |

Add a `model: <model-id>` key to any entry in `models.yaml` to pin a specific Claude model; omit it to use the CLI default.

### Recommended run sequences

```bash
# 1. Dry-run first — verifies harness setup without spending tokens
python3 benchmark/run.py run-suite --model claude-full-harness --mode dry

# 2. Cheap smoke run with Haiku
python3 benchmark/run.py run-suite --model claude-haiku-full-harness --mode live

# 3. Full Sonnet comparison (3 configs × 12 tasks)
python3 benchmark/run.py run-suite --model claude-no-harness --mode live
python3 benchmark/run.py run-suite --model claude-full-harness --mode live
python3 benchmark/run.py run-suite --model claude-full-harness-rtk --mode live

# 4. Resume an interrupted suite
python3 benchmark/run.py run-suite --model claude-full-harness --from-task C-explanation-001
```

## Directory layout

```
benchmark/
  clawbench_v2/           harness-bench runtime (copied + extended)
    adapters/
      claude_code.py      Claude Code adapter (uses harness_config)
      codex.py            Codex adapter (uses harness_config)
      _harness_setup.py   Shared harness setup logic (mint, rtk, minimal)
  config/
    app.yaml              tasks/results/work paths, timeout
    models.yaml           per-model adapter + harness_config
  tasks/
    A_bug_fix/            task dir (task.yaml + prompt.txt + fixtures/ + oracle_grade.py)
    B_implementation/     task dir
  fixtures/
    target_project/       shared fixture source — Python project with deliberate bugs
    configs/minimal/      CLAUDE.md + AGENTS.md for minimal config
  results/                per-model result JSON files (gitignored)
  probe/                  generated depth/clarity smoke probe
  scenarios/              legacy scenario files (kept for backward compat)
  runner/                 legacy runner code (kept for backward compat)
  run.py                  thin CLI wrapper — delegates to clawbench_v2.cli
```

## How it works

1. `run.py` sets `CLAWBENCHV2_APP_CONFIG` + `CLAWBENCHV2_MODELS_CONFIG` and delegates to `clawbench_v2.cli`
2. The runner copies the task's `fixtures/` into a fresh sandbox under `/tmp/harness-bench-work/`
3. The adapter runs the agent against the sandbox workspace, applying the harness config
4. The oracle (`oracle_grade.py`) runs `pytest` in the workspace and returns a score
5. Results are saved as JSON in `benchmark/results/<model_id>/<task_id>.json`

## Probe benchmark

`benchmark/probe/` contains a generated depth/clarity smoke benchmark. It builds
a temporary Python call chain with a terminal arithmetic defect, optionally
scrambles symbols, and asks the agent to make pytest pass.

Use it to check adapter wiring, generated-workspace validity, and rough
token/latency overhead:

```bash
python3 benchmark/probe/run_probe.py \
  --models codex-no-harness,codex-full-harness \
  --depths 7,9 \
  --clarities 0.25,0.0 \
  --reps 1 \
  --mode live
```

Current interpretation: keep this as a smoke benchmark, not as a headline
capability benchmark. On 2026-06-17, Codex passed every attempted probe up to
depth 9 with full symbol scrambling, so the probe did not separate baseline
from full harness. It did show substantial full-harness token and latency
overhead. See `benchmark/probe/README.md` for results and recommendations.

## Adding a new task

1. Create `benchmark/tasks/<NAME>/`
2. Write `task.yaml`:
   ```yaml
   task_id: "My-task-001"
   title: "Task description"
   prompt_files: ["prompt.txt"]
   fixtures_dir: "fixtures"
   oracle_module: "oracle_grade.py"
   timeout_sec: 300
   tags: ["category"]
   ```
3. Write `prompt.txt` — the task description given to the agent
4. Copy or create `fixtures/` — the project the agent will work in
5. Write `oracle_grade.py` with a `score_workspace(workspace: Path) -> dict` function
   that returns at least `{"outcome_score": float, "passed": bool}`

## Adding a new model

Add an entry to `benchmark/config/models.yaml`:
```yaml
my-model-id:
  adapter: claude_code        # or codex
  harness_config: full_harness
  timeout_sec: 300
```

## Legacy runner (old scenarios)

The original scenario-based runner still works:
```bash
# Run all scenarios across all configs with Claude
python benchmark/run.py --legacy

# Run with one config
python benchmark/run.py --config full_harness

# Run a single scenario
python benchmark/run.py --scenario A_bug_fix/001
```

The legacy runner lives in `benchmark/runner/` and uses `benchmark/scenarios/`.
