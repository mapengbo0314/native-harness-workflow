# Bundle Fallback and Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a fallback mechanism in `harness-wf init` to correctly resolve the `--bundle` path and prompt the user to generate an index if none exists.

**Architecture:** We will intercept the initialization process in `cli.py` *before* hitting the discovery engine. We will check the provided bundle path or the default `.codegraph` directory for wiki files. If missing, we prompt the user to run `CodeGraph wiki generate` using the collected LLM credentials, and then pass the resolved bundle path down to the discovery engine.

**Tech Stack:** Python, argparse, subprocess

---

### Task 1: Update `discovery_engine.py` to accept `bundle_path`

**Files:**
- Modify: `harness/discovery_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# test_discovery_engine.py (concept, assuming we have tests for this)
import os
import tempfile
from harness.discovery_engine import acquire_mcp_context

def test_acquire_mcp_context_with_bundle():
    with tempfile.TemporaryDirectory() as temp_dir:
        bundle_dir = os.path.join(temp_dir, "my_bundle")
        wiki_dir = os.path.join(bundle_dir, "wiki")
        os.makedirs(wiki_dir)
        with open(os.path.join(wiki_dir, "index.md"), "w") as f:
            f.write("Bundle Index")
        with open(os.path.join(wiki_dir, "architecture.md"), "w") as f:
            f.write("Bundle Arch")

        # project_path is dummy, it should prioritize bundle
        context = acquire_mcp_context("/dummy/path", bundle_path=bundle_dir)
        assert "Bundle Index" in context
        assert "Bundle Arch" in context
```

- [ ] **Step 2: Write minimal implementation**

Modify `acquire_mcp_context` in `harness/discovery_engine.py`:

```python
def acquire_mcp_context(project_path: str, bundle_path: str = None) -> str:
    """Acquires lightweight project context from the core wiki files to avoid token explosion."""
    
    # Check bundle path first if provided
    if bundle_path:
        bundle_wiki_path = os.path.join(bundle_path, "wiki") if not bundle_path.endswith("wiki") else bundle_path
        # If the user passed the path to the CodeGraph folder itself
        if not os.path.exists(bundle_wiki_path) and os.path.basename(bundle_path) == ".codegraph":
            bundle_wiki_path = os.path.join(bundle_path, "wiki")
        elif not os.path.exists(bundle_wiki_path):
             bundle_wiki_path = os.path.join(bundle_path, ".codegraph", "wiki")

        if os.path.exists(bundle_wiki_path):
            wiki_path = bundle_wiki_path
            print(f"Found existing wiki in bundle at {wiki_path}. Reading core architecture...")
        else:
            wiki_path = os.path.join(project_path, ".codegraph", "wiki")
    else:
        wiki_path = os.path.join(project_path, ".codegraph", "wiki")

    context_parts = []
    
    if os.path.exists(wiki_path):
        if not bundle_path or wiki_path == os.path.join(project_path, ".codegraph", "wiki"):
             print(f"Found existing .codegraph/wiki at {wiki_path}. Reading core architecture...")
        
        # Read ONLY the index and architecture to avoid token explosion
        for core_file in ["index.md", "architecture.md"]:
            p = os.path.join(wiki_path, core_file)
            if os.path.exists(p):
                with open(p, 'r') as f:
                    context_parts.append(f"=== {core_file.upper()} ===\n" + f.read())
                    
        if context_parts:
            return "\n\n".join(context_parts)

    # Return None instead of a string if no wiki is found so caller can handle fallback
    return None
```

- [ ] **Step 3: Commit**

```bash
git add harness/discovery_engine.py
git commit -m "feat: update acquire_mcp_context to use bundle_path"
```

---

### Task 2: Implement fast-path check and fallback in `cli.py`

**Files:**
- Modify: `harness/cli.py`

- [ ] **Step 1: Write the failing test**

*(No formal unit tests exist for cli.py main function, we rely on manual verification for interactive CLI apps)*

- [ ] **Step 2: Write implementation**

Modify `harness/cli.py` inside `main()` immediately after setting up API keys, before Stage 1:

```python
    print("Pre-flight checks passed.")
    
    # --- New: Fast Path Bundle Resolution & Fallback ---
    resolved_bundle_path = None
    if args.bundle:
        resolved_bundle_path = os.path.abspath(args.bundle)

    # Check for index existence
    index_found = False
    
    # 1. Check bundle if provided
    if resolved_bundle_path:
        bundle_CodeGraph = resolved_bundle_path if os.path.basename(resolved_bundle_path) == ".codegraph" else os.path.join(resolved_bundle_path, ".codegraph")
        if os.path.exists(os.path.join(bundle_CodeGraph, "INDEX.md")) or os.path.exists(os.path.join(bundle_CodeGraph, "wiki", "index.md")):
            index_found = True
        elif os.path.exists(os.path.join(resolved_bundle_path, "INDEX.md")) or os.path.exists(os.path.join(resolved_bundle_path, "wiki", "index.md")):
            index_found = True # Handle direct path to wiki dir

    # 2. Check project path
    project_CodeGraph = os.path.join(args.project_path, ".codegraph")
    if not index_found and (os.path.exists(os.path.join(project_CodeGraph, "INDEX.md")) or os.path.exists(os.path.join(project_CodeGraph, "wiki", "index.md"))):
        index_found = True

    if not index_found:
        print("\nNo existing CodeGraph database found.")
        choice = input("Would you like to generate one now using 'CodeGraph wiki generate'? (Y/n): ").strip().lower()
        if choice in ['', 'y', 'yes']:
            print("Generating CodeGraph wiki...")
            
            # Prepare environment variables with the collected API key
            env = os.environ.copy()
            if args.llm == "anthropic":
                env["ANTHROPIC_API_KEY"] = api_key
            elif args.llm == "openai":
                env["OPENAI_API_KEY"] = api_key
            elif args.llm == "gemini":
                 # Currently CodeGraph wiki generate requires ANTHROPIC or OPENAI, but we pass what we have.
                 # If CodeGraph adds Gemini support, this will be needed.
                 env["GEMINI_API_KEY"] = api_key
                 # Fallback warning if Gemini is selected for harness but indexer needs Anthropic
                 if not env.get("ANTHROPIC_API_KEY") and not env.get("OPENAI_API_KEY"):
                      print("Warning: 'CodeGraph wiki generate' currently requires ANTHROPIC_API_KEY or OPENAI_API_KEY.")
            
            # Execute CodeGraph in the project directory
            try:
                # Use npx if CodeGraph is not installed globally, fallback to global CodeGraph if npx fails
                result = subprocess.run(
                    ["npx", "--yes", "CodeGraph", "wiki", "generate"], 
                    cwd=args.project_path, 
                    env=env,
                    check=False
                )
                if result.returncode != 0:
                     # Fallback to global CodeGraph
                     subprocess.run(
                        ["CodeGraph", "wiki", "generate"], 
                        cwd=args.project_path, 
                        env=env,
                        check=True
                     )
            except subprocess.CalledProcessError as e:
                print(f"\nFailed to generate CodeGraph wiki: {e}")
                print("Context will be severely limited.")
            except Exception as e:
                print(f"\nError running indexer: {e}")
                print("Context will be severely limited.")
        else:
             print("Proceeding without codebase index. Architecture context will be severely limited.")
    # --- End Fast Path ---

    print("Stage 1: Cloning boilerplate for discovery...")
```

Update the `acquire_mcp_context` call in `main()` to use the resolved bundle and handle the new `None` return:

```python
        # Acquire context once
        context_str = acquire_mcp_context(args.project_path, bundle_path=resolved_bundle_path)
        if context_str is None:
             context_str = "No codebase wiki found. Architecture unknown."
             print("No usable .codegraph/wiki found. Proceeding with empty context.")
```

Update the `mint_workspace` call in `main()` to use the resolved bundle:

```python
        mint_workspace(target_dir, selected_agents, args.project_path, platform_choice, args.model, resolved_bundle_path, boilerplate_dir, ddd_context=final_ddd_context)
```

- [ ] **Step 3: Commit**

```bash
git add harness/cli.py
git commit -m "feat: add fast path index check and generation fallback"
```

---

### Task 3: Ensure `minting_engine.py` uses correct bundle logic

**Files:**
- Modify: `harness/minting_engine.py`

- [ ] **Step 1: Write minimal implementation**

We need to ensure `minting_engine.py` correctly handles the absolute path we are passing it. It already has logic for `bundle_override`, but let's make sure it handles absolute paths seamlessly.

*(The existing logic in `minting_engine.py`:)*
```python
    if bundle_override:
        # Determine where the .codegraph folder is located based on the bundle argument
        if os.path.isdir(bundle_override) and os.path.basename(bundle_override) == ".codegraph":
            source_CodeGraph = bundle_override
        elif os.path.isdir(bundle_override):
            source_CodeGraph = os.path.join(bundle_override, ".codegraph")
        else:
            source_CodeGraph = os.path.join(os.path.dirname(bundle_override), ".codegraph")
            
        target_CodeGraph = os.path.join(project_path, ".codegraph")
```
*Self-Correction: The existing logic handles absolute paths perfectly because `os.path.join` on an absolute path drops previous segments, and since we are passing an absolute path from `cli.py`, this logic holds up.*

No code changes are strictly necessary for `minting_engine.py` regarding path resolution since we resolve it in `cli.py` before passing it down. However, verify the logic works during manual testing.

- [ ] **Step 2: Commit**

*(No commit needed if no changes made)*