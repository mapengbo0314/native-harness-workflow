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
    parser.add_argument("--model", help="Optional specific model to use (e.g., gemini-3.1-pro-preview, claude-3-5-sonnet-20241022)")
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
    codegraph_db_path = os.path.join(args.project_path, ".codegraph", "codegraph.db")
    if not os.path.exists(codegraph_db_path):
        print(f"\nCodeGraph database not found. Building now...")
        try:
            # Force non-interactive npm to prevent hidden prompts
            env = os.environ.copy()
            env["npm_config_yes"] = "true"
            
            subprocess.run(
                ["npx", "--yes", "@colbymchenry/codegraph", "init", "--index"],
                cwd=args.project_path,
                env=env,
                check=True
            )
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
    from harness.discovery_engine import acquire_mcp_context, generate_onboarding_domain_doc
    
    # Acquire context once
    context_str = acquire_mcp_context(args.project_path)
    if context_str is None:
         context_str = "No codebase context found. Architecture unknown."
         print("Proceeding with empty context.")
    

    # CLI Context Wizard (The 3 Questions)
    print("\n--- Project Context Setup ---")
    purpose = input("1. In 1-2 sentences, what is the core purpose of this project?\n> ")
    vocab = input("2. What are 2-3 specific vocabulary terms (Ubiquitous Language) used in this codebase?\n> ")
    invariants = input("3. Are there any strict architectural rules or invariants? (e.g., 'Never delete users, only deactivate')\n> ")
    
    # Save to docs/domain/CONTEXT.md
    context_dir = os.path.join(args.project_path, "docs", "domain")
    os.makedirs(context_dir, exist_ok=True)
    with open(os.path.join(context_dir, "CONTEXT.md"), "w") as f:
        f.write(f"# Project Context\n\n## Purpose\n{purpose}\n\n## Ubiquitous Language\n{vocab}\n\n## Strict Invariants\n{invariants}\n")


    selected_agents = []

    print("\n=== Platform Selection ===")
    print("1. Gemini CLI")
    print("2. Claude Code")
    print("3. Cursor")
    print("4. Generic / Custom")
    print("5. Codex")
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

    target_dir = os.path.join(args.project_path, harness_folder)
    
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
    generate_onboarding_domain_doc(
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

    # We pass the bundled boilerplate_dir
    mint_workspace(target_dir, selected_agents, args.project_path, platform_choice, args.model, boilerplate_dir)

    # Install tools
    install_workspace_tools(args.project_path, harness_folder, skills_to_install, mcps_to_install)

    # Determine subagent syntax for rule patching
    target_syntax = "@"
    if platform_choice == "2": # Claude
        target_syntax = "Task tool: "
    elif platform_choice == "5": # Codex
        target_syntax = "Hand off to "

    sme_agent_name = synthesize_domain_sme_agent(args.project_path, domain_content, harness_folder, platform_choice=platform_choice, model_choice=args.model)
    patch_orchestrator_rules(args.project_path, sme_agent_name, harness_folder, target_syntax=target_syntax)

    # --- Plugin Generation for Claude Code ---
    from harness.minting_engine import should_generate_orchestrator_plugin
    from harness.plugin_generator import generate_orchestrator_plugin
    
    plugin_dir = None
    if should_generate_orchestrator_plugin(domain_content, platform_choice):
        try:
            print(f"\n[{'='*60}]\n[HARNESS] Generating orchestrator plugin...")
            plugin_dir = generate_orchestrator_plugin(
                project_path=str(args.project_path),
                project_name=os.path.basename(args.project_path),
                boilerplate_dir=boilerplate_dir
            )
            
            # Post-generation cleanup for Claude: remove top-level agents and skills
            # as they are now inside the plugin
            harness_path = Path(target_dir)
            for folder in ["agents", "skills"]:
                folder_path = harness_path / folder
                if folder_path.exists():
                    shutil.rmtree(folder_path)
            print("[HARNESS] Cleaned up redundant top-level folders for Claude plugin.")
            
        except Exception as e:
            print(f"\n[HARNESS] ❌ ERROR: Failed to generate orchestrator plugin: {e}")
            print("[HARNESS] Traceback for diagnosis:")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    # --- End Plugin Generation ---

    print(f"\n\n{'='*60}")
    print("🚀 ONBOARDING COMPLETE")
    print(f"\n{'='*60}")
    
    counter = 1
    print(f"\n\n{counter}. Workspace Minted: {target_dir}")
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
