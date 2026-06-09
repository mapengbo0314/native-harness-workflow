# Benchmark Target Project

Minimal synthetic codebase used as the target for harness benchmark runs.
Do not modify — changes affect benchmark reproducibility.

## Deliberate defects

| File | Defect | Used by |
|---|---|---|
| `src/auth.py` | `login()` raises `TypeError` for unknown users instead of `ValueError` | Scenario A-001 |
| `src/data_table.py` | `export_csv()` not implemented (TODO stub) | Scenario B-001 |
