# QA Report: Onboarding Enhancement Project (`harness/cli.py`)

## 1. Regression Testing
**Command:** `PYTHONPATH=. pytest tests/ -v`
**Result:** 26/26 tests passed (0 failures).
**Evidence:** 
```
tests/test_core_mandates_presence.py::test_core_mandates_file_exists PASSED
tests/test_discovery_engine.py::test_discover_agents PASSED
tests/test_discovery_engine.py::test_generate_onboarding_domain_doc PASSED
tests/test_minting_engine.py::test_parse_tool_checklists PASSED
...
============================= 26 passed in 0.09s ==============================
```

## 2. Functional Verification
The newly added onboarding logic works as intended. Code analysis of `harness/cli.py` and unit tests in `tests/test_minting_engine.py` verify the following flow:
1. **Tool Discovery:** `discovery_engine.py` correctly queries the LLM and formats checklists into `ONBOARDING_DOMAIN.md`.
2. **Review Pause:** `minting_engine.py:wait_for_user_review_and_read_domain` correctly pauses for the user via `input()` and reads the updated Markdown file.
3. **Checklist Parsing:** `parse_tool_checklists` extracts selected tools (`- [x]`) using robust regex parsing.
4. **Tool Installation:** `install_workspace_tools` successfully fetches remote skills via `urllib` and configures MCP arguments locally into the `mcp.json` and `skills.json` within the newly minted workspace without global pollution.
5. **SME Synthesis:** `synthesize_domain_sme_agent` builds and registers the rigid `@domain-sme` agent and patches it into the `dispatch_rules.md`.
6. **Final Summary:** The CLI script correctly lists the minted agents, installed skills, configured MCPs, and prints specific MCP authorization instructions depending on the chosen platform.

## 3. Edge Case Verification
- **Missing API Keys:** `harness/cli.py` (L59) successfully prompts via `getpass` if the required `{LLM}_API_KEY` environment variable is not found. An invalid key results in a clean runtime exception handled gracefully by the script (verified via subprocess test logging `API_KEY_INVALID` and raising `RuntimeError: Gemini API call failed`).
- **Failed Indexer Generation:** `harness/cli.py` (L122) catches `subprocess.CalledProcessError`, `FileNotFoundError`, and standard exceptions during `CodeGraph wiki generate`. It warns the user ("Context will be severely limited.") and proceeds without crashing. 
- **No Agents Selected:** The CLI correctly evaluates the boolean `if not selected_agents:` (L208) and exits cleanly with `sys.exit(0)` and the message "No agents selected. Aborting." if the user types 'n' to all recommendations.
- **Missing Tool JSONs:** `install_workspace_tools` manages file absence gracefully; if `skills.json` or `mcp.json` don't exist, it instantiates empty JSON structures and dumps the configured objects, preventing `FileNotFoundError` or decode failures.

## Verification Verdict
**PASS**
