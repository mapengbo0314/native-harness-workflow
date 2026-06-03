# Harness Benchmark

Compares harness performance across three configurations:

| Config | What it is |
|---|---|
| `no_harness` | Raw Claude, no context |
| `minimal` | `CLAUDE.md` + `AGENTS.md` only |
| `full_harness` | Full plugin (`harness-wf-plugin`) installed |

## Run

```bash
pip install anthropic pyyaml
python benchmark/run.py
```

Run a single config:
```bash
python benchmark/run.py --config full_harness
```

Run a single scenario:
```bash
python benchmark/run.py --scenario A_bug_fix/001
```

## How it works

1. Each scenario in `scenarios/` has a prompt (`.md`) and acceptance criteria (`.yaml`)
2. The runner spawns a `claude --print` session with `HARNESS_SESSION_ID` set for Langfuse correlation
3. The scorer uses Claude Opus as a judge to evaluate each criterion against the transcript
4. Results are saved to `results/` (gitignored) and printed as a summary table

## Scenarios

Organised by prompt category matching the harness classifier:

- `A_bug_fix/` — debugging and error diagnosis
- `B_implementation/` — new features and implementation tasks
- `C_explanation/` — how-does-X-work questions
- `E_misc/` — off-topic and miscellaneous

## Adding scenarios

1. Add `NNN_description.md` with the prompt
2. Add `NNN_criteria.yaml` with weighted acceptance criteria
3. Run to verify it scores correctly against `full_harness`
