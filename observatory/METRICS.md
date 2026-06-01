# Observatory Metrics Reference

## Harness Status

Shows whether the native harness plugin is installed in each repo and whether it is current.

| State | Meaning |
|---|---|
| `v0.1.0 ✓` | Installed and up to date with `native-harness-workflow` |
| `v0.1.0 → v0.2.0` | Installed but behind — reinstall with `harness-wf init` |
| `no harness` | Plugin not found in `.claude/` |

The current version is read from `harness_source_path` in `repos.yaml`. The installed version is read from `.harness-meta.json` inside the plugin directory.

---

## AI Commit Percentage

Fraction of commits in the last 12 weeks that are AI-assisted, detected by co-author patterns in commit messages (e.g. `Co-Authored-By: Claude`).

Patterns are configured in `benchmarks.yaml` under `ai_patterns`.

High AI% is not inherently good or bad — it is a signal of adoption. Combine with rework rate and commit size to interpret quality.

---

## Commits per Week

Sparkline of weekly commit volume over the last 12 weeks. `commits_last_30d` is the sum of the last 4 buckets.

---

## Commit Size (p50 / p90)

Median and 90th-percentile churn (additions + deletions) per commit, computed from the deep scan cache.

| Threshold | p50 | p90 |
|---|---|---|
| Healthy | < 50 | < 300 |
| Warning | 50–150 | 300–800 |
| Critical | > 150 | > 800 |

Thresholds are configurable in `benchmarks.yaml`. Large commits are a signal of insufficient task decomposition — a key harness behaviour to improve.

---

## Rework Rate

Fraction of commits that touch a file within 14 days of a prior commit touching the same file. A proxy for churn and incomplete first-pass implementation.

| Threshold | Rate |
|---|---|
| Healthy | < 15% |
| Warning | 15–30% |
| Critical | > 30% |

Requires a completed deep scan. Shown as `—` until the scan finishes.

---

## Open PRs

Current count of open pull requests fetched live from GitHub.

---

## Deep Scan

A background scan that walks the full commit history to compute commit size and rework rate. Triggered manually per repo. Shows progress (`scanning 142/800`) and last scan timestamp.

Scan state is stored in a local SQLite database (`observatory.db`), not in GitHub.

---

## Agent Files

Presence of agent configuration files in the repo (e.g. `AGENTS.md`, `CLAUDE.md`). Indicates baseline agentic setup independent of the harness plugin.
