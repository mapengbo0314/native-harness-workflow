---
name: continuous-learning
description: Manual on-demand skill learning and extraction. Run this skill or type /learn to manually trigger the extraction of newly acquired engineering skills and insights from the current session transcript.
---

# Continuous Learning

Manually extract, synthesize, and record newly learned codebase structures, design patterns, or engineering instincts from the current conversation.

## When to Use
Use when:
- You have just finished a complex implementation, bug fix, or design discussion and want to immediately capture the learnings rather than waiting for the session to end.
- You want to force on-demand extraction of a highly validated pattern before proceeding.

## Protocol
1. To invoke on-demand, execute the `/learn` command or explicitly trigger this skill.
2. The agent will read the transcript of the current session, analyze the technical problem solved, identify unique design choices or debug instincts, and save the resulting SKILL.md file to the out-of-repo project store under `~/.local/share/harness-wf/projects/<repo-hash>/learned/`.
3. The newly learned skill will automatically be injected into future sessions.
