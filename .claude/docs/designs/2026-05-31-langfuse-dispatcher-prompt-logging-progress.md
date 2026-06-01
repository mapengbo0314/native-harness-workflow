# Langfuse Dispatcher Prompt Logging — Task Progress

**Design:** `.claude/docs/designs/2026-05-31-langfuse-dispatcher-prompt-logging-design.md`
**Branch:** `feat/langfuse-dispatcher-prompt-logging`
**Base SHA:** `2135ef0`

## Tasks

### L-T1: Add `complete_prompt_span` to `langfuse_instrumentation.py`
**Status:** pending
**Files:** `src/harness/runtime/langfuse_instrumentation.py`, `.claude/harness-wf-plugin/src/langfuse_instrumentation.py`

### L-T2: Call `complete_prompt_span` in `prompt_classifier.py`
**Status:** pending
**Files:** `.claude/harness-wf-plugin/hooks/prompt_classifier.py`
**Depends on:** L-T1

### L-T3: Add structured `input`/`output` to `dispatch_agent` in `dispatcher.py`
**Status:** pending
**Files:** `src/harness/runtime/dispatcher.py`, `.claude/harness-wf-plugin/src/dispatcher.py`
