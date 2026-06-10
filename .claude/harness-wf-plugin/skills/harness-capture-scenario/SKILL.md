---
name: harness-capture-scenario
description: Capture an observed harness failure or unexpected behavior as a replayable benchmark scenario in the harness repo
---

# Capture a Harness Scenario

Use this skill when you observe the harness behaving unexpectedly — wrong routing, skipped
workflow steps, looping, ignored instructions, bad output, or anything worth tracking.

You do not need prior context about the harness repo. Follow these steps exactly.

---

## Step 1 — Gather the facts before running anything

Answer these before proceeding:

| Field | Question |
|---|---|
| **prompt** | What was the exact user prompt that triggered the behavior? |
| **what happened** | What did the harness actually do? (e.g. routed to branch C, skipped TDD, looped 5 times) |
| **what should have happened** | What was the correct behavior? |
| **expected branch** | A / B / C / D / E — or unknown |
| **failure type** | `routing` / `workflow` / `output` / `loop` / `instruction` / `unknown` |
| **severity** | `high` (blocks work) / `medium` (degrades quality) / `low` (minor) |

If you are unsure about expected branch or failure type, use `unknown` — do not guess.

---

## Step 2 — Locate the harness repo

Check in this order and stop at the first that works:

1. **Environment variable** — if `HARNESS_REPO_ROOT` is set, use that path.
2. **Parent directory** — check `../native-harness-workflow/scripts/capture_scenario.py`
3. **Workspace search** — run:
   ```bash
   find ~/Workspace -name "capture_scenario.py" -maxdepth 5 2>/dev/null | head -1
   ```

If none of these find `capture_scenario.py`, stop and tell the user:
> "Could not locate the harness repo. Set HARNESS_REPO_ROOT in your .env pointing to the native-harness-workflow directory."

---

## Step 3 — Run the capture script

From the **current project directory**, run:

```bash
python <HARNESS_REPO_ROOT>/scripts/capture_scenario.py \
  --project . \
  --name <short-slug-no-spaces> \
  --failure-type <failure_type> \
  --severity <severity> \
  --expected-branch <branch-or-omit-if-unknown> \
  --description "<one sentence: what went wrong>" \
  --prompt "<the exact prompt>"
```

Use `--no-snapshot` if you want to skip file snapshotting and fill in files manually later.

The script writes the scenario YAML to:
```
<HARNESS_REPO_ROOT>/tests/sandbox/scenarios/captured/<name>.yaml
```

---

## Step 4 — Review the generated YAML

Open the file and verify:

- `files` section contains the relevant context (trim large files to the relevant parts only)
- `description` is accurate
- `failure_type` and `severity` are correct
- `expected_behavior.branch` matches what you intended

If files are missing or irrelevant, edit the YAML directly before committing.

---

## Step 5 — Commit and push

```bash
cd <HARNESS_REPO_ROOT>
git add tests/sandbox/scenarios/captured/<name>.yaml
git commit -m "capture: <name> — <one-line description>"
git push fork feat/benchmark-capture-pipeline
```

If `feat/benchmark-capture-pipeline` does not exist locally, push to `main` instead.

---

## Reference — failure types

| Type | When to use |
|---|---|
| `routing` | Wrong branch or agent selected (e.g. went to C instead of D) |
| `workflow` | Correct branch but skipped a required step (e.g. no plan doc, no TDD) |
| `output` | Correct workflow but produced bad code / failing tests |
| `loop` | Agent repeated the same tool call or flip-flopped between states |
| `instruction` | Agent ignored or weakened a mandate from the system prompt |
| `unknown` | Something was wrong but you cannot classify it yet |