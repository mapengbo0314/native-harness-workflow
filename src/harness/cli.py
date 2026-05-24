import argparse
import sys
import getpass
import os
import tempfile
import subprocess
import shutil
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(description="Initialize a new Harness agent workspace.")
    parser.add_argument("command", choices=["init"], help="Command to run")
    parser.add_argument("--project-path", required=True, help="Path to the repository")
    parser.add_argument("--llm", required=True, choices=["gemini", "openai", "anthropic"], help="LLM provider")
    parser.add_argument("--model", help="Optional specific model to use (e.g., gemini-2.0-flash, claude-3-5-sonnet-20241022)")
    parser.add_argument("--bundle", help="Path to an existing CodeGraph bundle (.codegraph directory)")
    return parser.parse_args()


def main():
    args = parse_args()

    if not shutil.which("npx"):
        print("\nError: 'npx' command not found. Node.js is required to use CodeGraph.")
        sys.exit(1)
    
    api_key_env_var = f"{args.llm.upper()}_API_KEY"
    api_key = os.environ.get(api_key_env_var)
    
    # Fallback for Gemini
    if not api_key and args.llm == "gemini":
        api_key = os.environ.get("GOOGLE_API_KEY")
        
    if not api_key:
        print(f"\nEnvironment variable {api_key_env_var} not found.")
        api_key = getpass.getpass(prompt=f"Enter your {args.llm} API Key: ")
        
    print("Pre-flight checks passed.")
    
    # --- CodeGraph Onboarding & Initialization ---
    default_codegraph_dir = os.path.join(args.project_path, ".codegraph")
    codegraph_dir = args.bundle if args.bundle else default_codegraph_dir
    codegraph_db_path = os.path.join(codegraph_dir, "codegraph.db")
    
    if not os.path.exists(codegraph_db_path):
        # If user specified a bundle path that isn't the project default and it's missing, that's a hard error
        if args.bundle and os.path.abspath(args.bundle) != os.path.abspath(default_codegraph_dir):
            print(f"\nError: Specified CodeGraph bundle not found at {codegraph_db_path}")
            sys.exit(1)
            
        print(f"\nCodeGraph database not found. Building now in project root...")
        try:
            # Force non-interactive npm to prevent hidden prompts
            env = os.environ.copy()
            env["npm_config_yes"] = "true"
            env["CODEGRAPH_DEBUG"] = "1"
            
            subprocess.run(
                ["npx", "--yes", "@colbymchenry/codegraph", "init", "--index"],
                cwd=args.project_path,
                env=env,
                check=True
            )
            # After building, ensure we use the newly created default dir
            codegraph_dir = default_codegraph_dir
            codegraph_db_path = os.path.join(codegraph_dir, "codegraph.db")
        except subprocess.CalledProcessError as e:
            print(f"\nFailed to build CodeGraph: {e}")
            sys.exit(1)

    print("Stage 1: Resolving bundled boilerplate...")
    from harness.utils import get_boilerplate_dir
    boilerplate_dir = str(get_boilerplate_dir())
    
    if not os.path.exists(boilerplate_dir):
        print(f"\nError: Bundled boilerplate not found at {boilerplate_dir}")
        sys.exit(1)
        
    print("Stage 2: Dynamic Context Acquisition")
    from harness.discovery_engine import acquire_mcp_context, generate_onboarding_domain_doc, generate_grilling_questions, synthesize_grilled_context, query_llm
    
    # Acquire context once
    context_str = acquire_mcp_context(args.project_path)
    if context_str is None:
         context_str = "No codebase context found. Architecture unknown."
         print("Proceeding with empty context.")
    

    # CLI Context Wizard (Dynamic Grilling)
    print("\n--- Project Context Setup ---")
    context_dir = os.path.join(args.project_path, "docs", "domain")
    os.makedirs(context_dir, exist_ok=True)
    context_file = os.path.join(context_dir, "CONTEXT.md")

    if os.environ.get("HARNESS_HEADLESS") == "1":
        print("Headless mode: Using default project context placeholders.")
        with open(context_file, "w") as f:
            f.write("# Project Context\n\n## Purpose\nAutomated purpose\n\n## Ubiquitous Language\nAutomated vocab\n\n## Strict Invariants\nAutomated invariants\n")
    else:
        print("Analyzing project to generate specific questions...")
        questions = generate_grilling_questions(args.project_path, query_llm, args.llm, api_key, args.model)
        
        qa_pairs = []
        for i, q_data in enumerate(questions):
            print(f"\n{i+1}. {q_data['question']}")
            suggestions = q_data.get("suggestions", [])
            if suggestions:
                for j, sug in enumerate(suggestions):
                    print(f"   {chr(65+j)}) {sug}")
                
                ans = input("> ").strip()
                # Check if answer is a letter matching a suggestion
                if len(ans) == 1 and 'A' <= ans.upper() <= chr(64 + len(suggestions)):
                    ans = suggestions[ord(ans.upper()) - 65]
            else:
                ans = input("> ").strip()
            
            if not ans:
                ans = "[No answer provided]"
            qa_pairs.append((q_data['question'], ans))
        
        print("\nSynthesizing project context...")
        context_md = synthesize_grilled_context(args.project_path, qa_pairs, query_llm, args.llm, api_key, args.model)
        with open(context_file, "w") as f:
            f.write(context_md)

    # Refresh context_str with the newly created CONTEXT.md
    context_str = acquire_mcp_context(args.project_path)


    selected_agents = []

    print("\n=== Platform Selection ===")
    print("1. Gemini CLI")
    print("2. Claude Code")
    print("3. Cursor")
    print("4. Generic / Custom")
    print("5. Codex")
    
    if os.environ.get("HARNESS_HEADLESS") == "1":
        platform_choice = os.environ.get("HARNESS_PLATFORM", "1")
        print(f"Headless mode: Defaulting to platform choice ({platform_choice}).")
    else:
        platform_choice = input("Select target platform [1-5]: ").strip()
        if not platform_choice:
            platform_choice = "1"
    
    if platform_choice == "1":
        harness_folder = ".gemini"
    elif platform_choice == "2":
        harness_folder = ".claude"
    elif platform_choice == "3":
        harness_folder = ".cursor"
    elif platform_choice == "5":
        harness_folder = ".codex"
    else:
        harness_folder = ".agents"

    # Normalize project_path to avoid nesting if the user points directly to the harness folder
    # We check against ALL common harness folder names to be safe
    possible_harness_folders = [".gemini", ".claude", ".cursor", ".codex", ".agents"]
    abs_project_path = os.path.abspath(args.project_path)
    path_parts = Path(abs_project_path).parts
    if path_parts and path_parts[-1] in possible_harness_folders:
        print(f"\nNotice: You pointed to a harness folder '{path_parts[-1]}'. Backtracking to project root: {os.path.dirname(abs_project_path)}")
        args.project_path = os.path.dirname(abs_project_path)

    # --- Atomic Swap Setup ---
    import time
    target_harness_dir = Path(args.project_path) / harness_folder
    temp_harness_dir = Path(args.project_path) / ".harness_tmp"
    
    if temp_harness_dir.exists():
        shutil.rmtree(temp_harness_dir)
    temp_harness_dir.mkdir(parents=True)

    from harness.minting_engine import (
        mint_workspace,
        wait_for_user_review_and_read_domain,
        synthesize_domain_sme_agent,
        patch_orchestrator_rules,
        parse_tool_checklists,
        install_workspace_tools
    )

    print("\nStage 2.7: Phased Onboarding & Domain SME Discovery")
    from harness.discovery_engine import query_llm
    tech_stack_data = generate_onboarding_domain_doc(
        args.project_path, 
        "Analyzed Codebase Context", 
        query_llm, 
        args.llm, 
        api_key, 
        context_str,
        boilerplate_dir
    )
    domain_content = wait_for_user_review_and_read_domain(args.project_path)

    # Parse tools
    skills_to_install, mcps_to_install = parse_tool_checklists(domain_content)

    try:
        # We pass the bundled boilerplate_dir and target the temp directory
        mint_workspace(
            str(temp_harness_dir), 
            selected_agents, 
            args.project_path, 
            platform_choice, 
            args.model, 
            boilerplate_dir, 
            query_llm_fn=query_llm, 
            llm_provider=args.llm, 
            api_key=api_key, 
            tech_stack_data=tech_stack_data,
            logical_harness_name=harness_folder
        )

        # Install tools (targeting temp)
        install_workspace_tools(args.project_path, ".harness_tmp", skills_to_install, mcps_to_install)

        # Determine subagent syntax for rule patching
        target_syntax = "@"
        if platform_choice == "2": # Claude
            target_syntax = "Task tool: "
        elif platform_choice == "5": # Codex
            target_syntax = "Hand off to "

        # SME synthesis (targeting temp)
        sme_agent_name = synthesize_domain_sme_agent(args.project_path, domain_content, ".harness_tmp", platform_choice=platform_choice, model_choice=args.model, logical_harness_name=harness_folder)
        patch_orchestrator_rules(args.project_path, sme_agent_name, ".harness_tmp", target_syntax=target_syntax)

        # --- Plugin Generation (targeting temp) ---
        from harness.minting_engine import should_generate_orchestrator_plugin
        from harness.plugin_generator import generate_orchestrator_plugin
        
        plugin_dir = None
        if should_generate_orchestrator_plugin(domain_content, platform_choice):
            try:
                print(f"\n[{'='*60}]\n[HARNESS] Generating orchestrator plugin...")
                plugin_dir = generate_orchestrator_plugin(
                    project_path=str(args.project_path),
                    project_name=os.path.basename(args.project_path),
                    boilerplate_dir=boilerplate_dir,
                    harness_folder=".harness_tmp"
                )
                
                # Post-generation cleanup: remove top-level agents and skills
                # as they are now inside the plugin
                harness_path = temp_harness_dir
                for folder in ["agents", "skills"]:
                    folder_path = harness_path / folder
                    if folder_path.exists():
                        shutil.rmtree(folder_path)
                print("[HARNESS] Cleaned up redundant top-level folders for plugin.")
                
            except Exception as e:
                print(f"\n[HARNESS] ❌ ERROR: Failed to generate orchestrator plugin: {e}")
                import traceback
                traceback.print_exc()
                sys.exit(1)
        
        # --- Handle Root Staging ---
        root_staging_dir = temp_harness_dir / "root_staging"
        if root_staging_dir.exists():
            from harness.minting_engine import merge_markdown, merge_structured
            print(f"\n[HARNESS] Found root staging files. Merging into project root...")
            for root, _, files in os.walk(root_staging_dir):
                for file in files:
                    staged_pointer = Path(root) / file
                    rel_path = staged_pointer.relative_to(root_staging_dir)
                    real_root_file = Path(args.project_path) / rel_path
                    
                    if real_root_file.exists():
                        # Merge existing with staged
                        try:
                            with open(real_root_file, 'r', encoding='utf-8') as f:
                                old_content = f.read()
                            with open(staged_pointer, 'r', encoding='utf-8') as f:
                                new_content = f.read()
                            
                            if file.endswith('.md'):
                                merged = merge_markdown(old_content, new_content)
                            elif file.endswith(('.json', '.yaml', '.yml')):
                                fmt = 'json' if file.endswith('.json') else 'yaml'
                                merged = merge_structured(old_content, new_content, format=fmt)
                            else:
                                # For other files, default to overwrite with new
                                merged = new_content
                                
                            with open(real_root_file, 'w', encoding='utf-8') as f:
                                f.write(merged)
                            print(f"[HARNESS] Merged {rel_path} into project root.")
                        except Exception as e:
                            print(f"[HARNESS] Warning: Failed to merge {rel_path}: {e}")
                    else:
                        # Move to real root
                        real_root_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(staged_pointer), str(real_root_file))
                        print(f"[HARNESS] Moved {rel_path} to project root.")
            
            shutil.rmtree(root_staging_dir)

        # --- Atomic Swap Execution ---
        if target_harness_dir.exists():
            from harness.minting_engine import perform_smart_merge
            print(f"\n[HARNESS] Existing harness found at {harness_folder}. Performing smart merge...")
            perform_smart_merge(target_harness_dir, temp_harness_dir)
            
            backup_dir = Path(args.project_path) / f"{harness_folder}.backup.{int(time.time())}"
            shutil.move(str(target_harness_dir), str(backup_dir))
            print(f"[HARNESS] Existing harness backed up to {backup_dir.name}")

        shutil.move(str(temp_harness_dir), str(target_harness_dir))
    finally:
        if temp_harness_dir.exists():
            shutil.rmtree(temp_harness_dir)


    print(f"\n\n{'='*60}")
    print("🚀 ONBOARDING COMPLETE")
    print(f"\n{'='*60}")
    
    counter = 1
    print(f"\n\n{counter}. Workspace Minted: {target_harness_dir}")
    counter += 1
    
    if plugin_dir:
        print(f"\n{counter}. Orchestrator Plugin Generated: {plugin_dir}")
        counter += 1
    
    if sme_agent_name:
        print(f"\n{counter}. Domain SME Created: @{sme_agent_name}")
        counter += 1
    
    if skills_to_install:
        print(f"\n{counter}. Local Skills Installed: {', '.join([s['name'] for s in skills_to_install])}")
        counter += 1
    
    if mcps_to_install:
        print(f"\n{counter}. MCP Tools Configured: {', '.join([m['name'] for m in mcps_to_install])}")
        print("\n[ACTION REQUIRED] MCP Authorization:")
        if platform_choice == "1":
            print("   - In Gemini CLI, you will be prompted to 'Allow' each tool on first use.")
        elif platform_choice == "2":
            print("   - In Claude Code, ensure you restart your session to load the new mcp.json.")
        print("   - Review your workspace mcp.json to verify the command paths.")
        counter += 1

    print(f"\n\n{counter}. [ACTION REQUIRED] Context Automation:")
    print("   - The CodeGraph CI GitHub Action (.github/workflows/codegraph-ci.yml) has been generated.")
    print("   - To enable automated context updates on PRs, configure the following GitHub Secrets:")
    print("     - GEMINI_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY")
    counter += 1

    if sme_agent_name:
        print(f"\n\n{counter}. Context: The @{sme_agent_name} is now the gateway for all planning.")
        print(f"\n   Dispatch rules in {harness_folder}/rules/dispatch_rules.md have been updated.")
        
    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    main()
