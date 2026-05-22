# Spec: Superpowers Agentic Harness Infrastructure Refactor

**Date:** 2026-05-22
**Status:** Draft / Pending Approval
**Topic:** Infrastructure Refactoring, Scalability, and LLM Evaluation

## 1. Problem Statement
The current infrastructure of the Superpowers Agentic Harness is brittle, heavily reliant on "magic" string replacements, and lacks clear organizational boundaries. The `tests/` directory is cluttered with maintenance scripts, and the state management system is prone to deadlocks and orphaned locks.

## 2. Proposed End-State Layout

```text
e-2-g/
├── .github/workflows/      # CI/CD (Codegraph, Benchmarks)
├── docs/
│   ├── domain/             # Project-specific DDD context
│   └── superpowers/specs/  # Architectural design docs
├── scripts/
│   └── maintenance/        # Formerly in tests/ (fix_*.py, patch_*.py)
├── src/
│   └── harness/            # Core Library
│       ├── templates/      # Jinja2 Boilerplate Agents
│       ├── cli.py          # Main entry point
│       ├── discovery.py    # DDD/Agent discovery
│       ├── minting.py      # Template rendering logic
│       ├── dispatcher.py   # Runtime state/routing
│       └── database.py     # SQLite/WAL logic
├── tests/
│   ├── unit/               # Pure logic tests
│   ├── integration/        # Generation tests (real FS via tmp_path)
│   ├── e2e/                # CLI subprocess tests
│   └── benchmarks/         # DeepEval configs & Eval data
├── mise.toml               # Task runner & build tracking
├── pyproject.toml          # PEP 621 metadata & dependencies
└── README.md
```

## 3. Design Sections

### Section 1: Repository Hygiene & Isolation
- **Decoupling:** Move `chat/` to a sibling directory `../chatbot`.
- **Packaging:** Move `boilerplate-agent/` into `src/harness/templates/`. This allows the harness to be distributed as a standalone package without runtime `git clone` dependencies.
- **Cleanup:** Purge `out/`, `artifacts/`, and `test_repro_dir/` from the repository and ignore them via `.gitignore`.

### Section 2: Core Logic (Templating & State)
- **Jinja2 Templating:** Replace all manual `.replace()` calls with a `Jinja2` rendering engine. 
    - *Delimiters:* Use `<!--% if %-->` and `<!--$ var $-->` to maintain valid Markdown previews.
- **SQLite State Management:** Replace `.harness_state.json.lock` with a local SQLite database.
    - **Concurrency:** Enable `PRAGMA journal_mode=WAL` for safe multi-agent access.
    - **Robustness:** Use TTL-based leases for agent locking. If an agent crashes, the lease expires, allowing the system to recover without manual intervention.

### Section 3: Testing & Task Orchestration
- **Mise Integration:** Use `mise` to track tasks (`test`, `lint`, `benchmark`).
- **Boundary Enforcement:**
    - **Unit:** Test classification logic and regex without IO.
    - **Integration:** Use `pytest.tmp_path` to verify that the `minting_engine` produces correct files on a real (temporary) filesystem.
    - **E2E:** Verify the CLI `init` flow from end-to-end.

### Section 4: Agentic Performance Suite (Evaluation)
- **Tooling:** Integrate **DeepEval** for automated agentic performance evaluation and regression testing.
- **Metrics:**
    - **Branching Accuracy:** Verify the dispatcher correctly routes tasks to Branch A/B/C/D based on intent.
    - **Routing Fidelity:** Verify the Orchestrator picks the correct specialized sub-agent (e.g., `@domain-sme`).
    - **Trajectory Check:** Ensure the "Planner -> Implementer" sequence is enforced.

## 4. Implementation Strategy
1. **Phase 1:** Extraction & Cleanup (`chat/`, junk files, `scripts/` migration).
2. **Phase 2:** Package Restructuring (Move to `src/`, relocate templates).
3. **Phase 3:** Core Engine Overhaul (Jinja2 & SQLite).
4. **Phase 4:** Performance Suite (Mise & DeepEval).

## 5. Success Criteria
- [ ] `harness-wf init` runs entirely offline using local templates.
- [ ] Zero orphaned lock files; system recovers automatically from agent crashes.
- [ ] `tests/` contains only test logic.
- [ ] Automated benchmark report verifies >90% branching accuracy via DeepEval.
