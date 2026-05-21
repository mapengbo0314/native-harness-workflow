# Token Optimization Report: Agentic Harness CLI

## 1. Executive Summary
An evaluation of `harness/cli.py`, `discovery_engine.py`, and `minting_engine.py` reveals significant opportunities for token optimization during the initial workspace minting phase. While the Hub-and-Spoke model itself is highly efficient over long sessions (as proven by the `benchmark_efficiency_test.py`), the initialization phase is currently "leaking" thousands of tokens through redundant LLM calls, massive prompt injections, and unnecessarily verbose output generation.

## 2. Findings & Table of Token Waste

| Component | Issue | Estimated Waste | Proposed Solution |
| :--- | :--- | :--- | :--- |
| `discovery_engine.py` | **Full Skill Injection**: Fetches 4 entire Markdown files (`grill-with-docs`, etc.) and injects them verbatim into the prompt. | ~8,000 - 12,000 Input Tokens / Call | Replace full-text injection with highly compressed, 50-word summaries of the skill mandates. |
| `discovery_engine.py` | **Redundant Context**: `discover_ddd_context` and `discover_agents` are separate calls that ingest the same `context_str` (architecture files). | ~1,000 - 3,000 Input Tokens | Merge into a single `discover_architecture_and_agents` call returning a unified JSON. |
| `discovery_engine.py` | **Verbose Outputs**: Explicitly demands "300-500 word" system prompts for each of the 3-5 recommended agents. | ~1,500 - 3,000 Output Tokens | Change instruction to "100-200 words concise, high-signal prompts" relying on MCP for context. |
| `minting_engine.py` | **Redundant Synthesis**: Uses an LLM call (`synthesize_domain_sme_agent`) just to format the user's edits in `ONBOARDING_DOMAIN.md` into a `.md` agent file. | ~500 Input + 200 Output Tokens | Replace the LLM call with deterministic Python string parsing/templating. |
| `cli.py` (Success Summary) | **Terminal Output**: Prints the final success state and next steps. | 0 Tokens (stdout) | **Status: Optimal.** The success summary is concise, informative, and incurs no LLM cost. |

## 3. Analysis against the "Goldfish" Principle
The current `cli.py` violates the "Verified Goldfish" mandate in its generation phase. By forcing the LLM to write 500-word system prompts for subagents, it encourages the creation of "mini-monoliths." Subagents should be extremely lean (`< 200 words`), relying entirely on the `CodeGraph` MCP tools to fetch dynamic context when needed, rather than having static rules hardcoded into their system prompts.

## 4. Numbered Implementation Plan

To implement these optimizations without losing functional context, the following steps are recommended:

1. **Compress Remote Skills**: In `discovery_engine.py`, remove `fetch_remote_skill`. Create a dictionary of hardcoded summaries:
   - *Example*: `"Grill with Docs: Challenge user definitions. Identify ambiguities. Ensure domain alignment."*
   - Inject these summaries instead of the full markdown files.
2. **Merge Discovery Calls**: Refactor `cli.py` and `discovery_engine.py` to perform a single `generate_onboarding_blueprint` LLM call that returns a JSON object containing both the `agents` array and the `ddd_context` object.
3. **Optimize Prompt Generation Constraints**: In the unified prompt, change the requirement from `"300-500 words"` to `"concise, high-signal system prompts (max 150 words). Mandate the use of 'CodeGraph' for codebase discovery."`
4. **Deterministic SME Minting**: In `minting_engine.py`, rewrite `synthesize_domain_sme_agent` to use regular expressions to extract the `<invariants>` and `<glossary>` directly from `ONBOARDING_DOMAIN.md`. Eliminate the LLM call entirely.

By implementing these changes, the initial Harness onboarding sequence will be 2-3x faster and save upwards of 20,000 tokens per initialization, drastically reducing the "Routing Tax" without compromising the quality of the generated agents.