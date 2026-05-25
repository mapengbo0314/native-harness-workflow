import argparse
import importlib.util
import json
import shlex
import sys
import getpass
import os
import subprocess
import shutil
import time
import uuid
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from langfuse.decorators import observe, langfuse_context

load_dotenv()


class HarnessSetupError(RuntimeError):
    """Raised when mandatory one-step harness setup cannot be completed."""


def _platform_name(platform_choice: str) -> str:
    return {
        "1": "gemini",
        "2": "claude",
        "3": "cursor",
        "4": "agents",
        "5": "codex",
    }.get(platform_choice, platform_choice).lower()


def _build_mcp_config(mcps_to_install: list[dict]) -> dict:
    mcp_servers = {
        "codegraph": {
            "command": "npx",
            "args": ["-y", "@colbymchenry/codegraph", "serve", "--mcp"],
        }
    }

    for mcp in mcps_to_install or []:
        command = mcp.get("command", "")
        try:
            parts = shlex.split(command)
        except ValueError as exc:
            raise HarnessSetupError(f"Invalid command string for MCP {mcp.get('name')}: {exc}") from exc
        if parts:
            mcp_servers[mcp["name"]] = {
                "command": parts[0],
                "args": parts[1:],
            }

    return {"mcpServers": mcp_servers}


def _write_repo_mcp_config(project_path: Path, mcps_to_install: list[dict]) -> None:
    mcp_path = project_path / ".mcp.json"
    new_config = _build_mcp_config(mcps_to_install)
    existing = {"mcpServers": {}}

    if mcp_path.exists():
        try:
            existing = json.loads(mcp_path.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        except json.JSONDecodeError as exc:
            raise HarnessSetupError(f"Existing .mcp.json is invalid JSON: {exc}") from exc

    existing.setdefault("mcpServers", {})
    existing["mcpServers"].update(new_config["mcpServers"])
    tmp_path = mcp_path.with_suffix(".tmp.json")
    tmp_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    os.replace(tmp_path, mcp_path)
    print("[HARNESS] Repo-level .mcp.json configured.")


def _configure_optional_platform_cli(project_path: Path, platform_choice: str, mcps_to_install: list[dict]) -> None:
    platform = _platform_name(platform_choice)
    if platform == "claude":
        claude = shutil.which("claude")
        if not claude:
            print("[HARNESS] Warning: 'claude' CLI not found. Generated .mcp.json is ready for Claude Code after restart.")
            return
        commands = [
            [claude, "mcp", "add", "codegraph", "npx", "-y", "@colbymchenry/codegraph", "serve", "--mcp"],
        ]
        for mcp in mcps_to_install or []:
            try:
                parts = shlex.split(mcp.get("command", ""))
            except ValueError as exc:
                raise HarnessSetupError(f"Invalid command string for MCP {mcp.get('name')}: {exc}") from exc
            if parts:
                commands.append([claude, "mcp", "add", mcp["name"], *parts])
        for command in commands:
            result = subprocess.run(command, cwd=project_path, capture_output=True, text=True, env=os.environ.copy())
            if result.returncode != 0:
                print(f"[HARNESS] Warning: Optional CLI MCP registration failed: {' '.join(command[:4])}")
        return

    if platform == "gemini":
        gemini = shutil.which("gemini")
        if not gemini:
            print("[HARNESS] Warning: 'gemini' CLI not found. Generated mcp.json files are ready for manual activation.")
            return
        commands = [
            [gemini, "mcp", "add", "codegraph", "npx", "-y", "@colbymchenry/codegraph", "serve", "--mcp"],
        ]
        for mcp in mcps_to_install or []:
            try:
                parts = shlex.split(mcp.get("command", ""))
            except ValueError as exc:
                raise HarnessSetupError(f"Invalid command string for MCP {mcp.get('name')}: {exc}") from exc
            if parts:
                commands.append([gemini, "mcp", "add", mcp["name"], *parts])
        for command in commands:
            result = subprocess.run(command, cwd=project_path, capture_output=True, text=True, env=os.environ.copy())
            if result.returncode != 0:
                print(f"[HARNESS] Warning: Optional CLI MCP registration failed: {' '.join(command[:4])}")


def _validate_claude_plugin(project_path: Path, plugin_dir: Path) -> None:
    required = [
        plugin_dir / ".claude-plugin" / "plugin.json",
        plugin_dir / "hooks" / "hooks.json",
        plugin_dir / "hooks" / "prompt_classifier.py",
        plugin_dir / "hooks" / "pre_tool_guard.py",
        plugin_dir / "hooks" / "post_tool_observer.py",
        plugin_dir / "hooks" / "precompact_handoff.py",
        plugin_dir / "hooks" / "stop_verifier.py",
        plugin_dir / "hooks" / "config_change_guard.py",
        plugin_dir / "src" / "dispatcher.py",
        plugin_dir / "config" / "ddd-context.json",
        plugin_dir / "agents",
        plugin_dir / "skills",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise HarnessSetupError("Generated plugin payload is incomplete:\n" + "\n".join(f"  - {path}" for path in missing))

    if (plugin_dir / "src" / "hooks").exists():
        raise HarnessSetupError("Legacy plugin src/hooks payload must not be generated.")

    config_text = "\n".join(path.read_text(encoding="utf-8") for path in (plugin_dir / "config").glob("*.json"))
    if ".harness_tmp" in config_text:
        raise HarnessSetupError("Generated plugin config contains staging path .harness_tmp.")

    dispatcher_path = plugin_dir / "src" / "dispatcher.py"
    spec = importlib.util.spec_from_file_location("harness_generated_plugin_dispatcher", dispatcher_path)
    if spec is None or spec.loader is None:
        raise HarnessSetupError(f"Could not load generated dispatcher at {dispatcher_path}")
    dispatcher_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dispatcher_module)

    json.loads((plugin_dir / "config" / "ddd-context.json").read_text(encoding="utf-8"))
    hooks_config = json.loads((plugin_dir / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    for groups in hooks_config.get("hooks", {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                command = hook.get("command", "")
                resolved = command.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_dir))
                try:
                    parts = shlex.split(resolved)
                except ValueError as exc:
                    raise HarnessSetupError(f"Invalid hook command string: {exc}") from exc
                script = Path(parts[1]) if len(parts) > 1 else None
                if (not script or not script.exists()) and len(parts) > 0 and Path(parts[0]).exists():
                    script = Path(parts[0])
                if not script or not script.exists():
                    raise HarnessSetupError(f"Hook command points at missing script: {command}")

    claude = shutil.which("claude")
    if claude:
        for target in [plugin_dir, project_path / ".claude"]:
            result = subprocess.run(
                [claude, "plugin", "validate", str(target), "--strict"], 
                capture_output=True, 
                text=True,
                env=os.environ.copy()
            )
            if result.returncode != 0:
                raise HarnessSetupError(result.stdout + result.stderr)

    print("[HARNESS] Claude plugin payload validated.")


def _write_setup_state(project_path: Path, harness_dir: Path, plugin_dir: Optional[Path], platform_choice: str) -> None:
    config_dir = (plugin_dir / "config") if plugin_dir and plugin_dir.exists() else (harness_dir / "config")
    config_dir.mkdir(parents=True, exist_ok=True)
    state_file = config_dir / ".harness_state.json"
    tmp_file = config_dir / ".harness_state.tmp.json"

    state = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                state = {}
        except json.JSONDecodeError:
            state = {}

    state.update({
        "setup_complete": True,
        "python_version": sys.version.split()[0],
        "platform": _platform_name(platform_choice),
        "codegraph_ready": True,
        "plugin_ready": bool(plugin_dir and plugin_dir.exists()),
        "strict_enforcement_enabled": bool(plugin_dir and plugin_dir.exists()),
        "repo_mcp_config": str(project_path / ".mcp.json"),
    })
    tmp_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp_file, state_file)
    print(f"[HARNESS] Setup state written to {state_file}.")


def run_embedded_setup(
    project_path: Path,
    harness_dir: Path,
    platform_choice: str,
    mcps_to_install: list[dict],
    plugin_dir: Optional[Path],
) -> None:
    print("\n[HARNESS] Running embedded setup...")
    if sys.version_info < (3, 8):
        raise HarnessSetupError("Python 3.8+ is required.")

    _write_repo_mcp_config(project_path, mcps_to_install)
    _configure_optional_platform_cli(project_path, platform_choice, mcps_to_install)
    if plugin_dir and plugin_dir.exists():
        _validate_claude_plugin(project_path, plugin_dir)
    _write_setup_state(project_path, harness_dir, plugin_dir, platform_choice)
    print("[HARNESS] Embedded setup complete.")


def parse_args():
    parser = argparse.ArgumentParser(description="Initialize a new Harness agent workspace.")
    parser.add_argument("command", choices=["init"], help="Command to run")
    parser.add_argument("--project-path", required=True, help="Path to the repository")
    parser.add_argument("--llm", required=True, choices=["gemini", "openai", "anthropic"], help="LLM provider")
    parser.add_argument("--model", help="Optional specific model to use (e.g., gemini-2.0-flash, claude-3-5-sonnet-20241022)")
    parser.add_argument("--bundle", help="Path to an existing CodeGraph bundle (.codegraph directory)")
    return parser.parse_args()


@observe()
def main():
    trace_id = os.environ.get("LANGFUSE_TRACE_ID")
    if not trace_id:
        trace_id = str(uuid.uuid4())
        os.environ["LANGFUSE_TRACE_ID"] = trace_id
        
    session_id = os.environ.get("LANGFUSE_SESSION_ID")
    if not session_id:
        session_id = str(uuid.uuid4())
        os.environ["LANGFUSE_SESSION_ID"] = session_id
        
    tags = []
    if os.environ.get("HARNESS_EVAL_MODE") == "1":
        env_tags = os.environ.get("LANGFUSE_TAGS")
        tags = env_tags.split(",") if env_tags else ["integration-test"]
        
    langfuse_context.update_current_trace(session_id=session_id, tags=tags)

    args = parse_args()

    if not shutil.which("npx"):
        print("\nError: 'npx' command not found. Node.js is required to use CodeGraph.")
        langfuse_context.flush()
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
            langfuse_context.flush()
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
            print(f"\nWarning: Failed to build CodeGraph: {e}")
            # Continuing without hard crash as per fallback behavior

    print("Stage 1: Resolving bundled boilerplate...")
    from harness.utils import get_boilerplate_dir
    boilerplate_dir = str(get_boilerplate_dir())
    
    if not os.path.exists(boilerplate_dir):
        print(f"\nError: Bundled boilerplate not found at {boilerplate_dir}")
        langfuse_context.flush()
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
            options = q_data.get("multiple_choice_options", [])
            if options:
                for j, opt in enumerate(options):
                    print(f"   {chr(65+j)}) {opt}")
                
                other_idx = len(options)
                other_letter = chr(65 + other_idx)
                print(f"   {other_letter}) Other [Please specify]")
                
                ans = input("> ").strip()
                # Check if answer is a letter matching an option
                if len(ans) == 1 and 'A' <= ans.upper() <= chr(64 + len(options)):
                    ans = options[ord(ans.upper()) - 65]
                elif len(ans) == 1 and ans.upper() == other_letter:
                    ans = input("Please specify: ").strip()
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
                    harness_folder=".harness_tmp",
                    logical_harness_name=harness_folder,
                )
                
                # Post-generation cleanup: remove boilerplate agents and skills
                # as they are now inside the plugin
                harness_path = temp_harness_dir
                
                sme_filename = f"{sme_agent_name}.md" if sme_agent_name else None
                
                # Clean agents folder
                agents_dir = harness_path / "agents"
                if agents_dir.exists():
                    shutil.rmtree(agents_dir)
                                
                # Clean skills folder
                skills_dir = harness_path / "skills"
                if skills_dir.exists():
                    shutil.rmtree(skills_dir)
                    
                print("[HARNESS] Cleaned up redundant top-level boilerplate folders for plugin.")
                
            except Exception as e:
                print(f"\n[HARNESS] ❌ ERROR: Failed to generate orchestrator plugin: {e}")
                import traceback
                traceback.print_exc()
                langfuse_context.flush()
                sys.exit(1)
        
        # --- Handle Root Staging ---
        root_staging_dir = temp_harness_dir / "root_staging"
        if root_staging_dir.exists():
            from harness.minting_engine import merge_markdown, merge_structured, handle_code_conflicts
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
                                # Prompt user for conflict resolution on other files
                                merged = handle_code_conflicts(old_content, new_content, str(rel_path))
                                
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
            
            # Keep only the latest 3 backups
            backups = sorted(Path(args.project_path).glob(f"{harness_folder}.backup.*"))
            for old_backup in backups[:-3]:
                shutil.rmtree(old_backup)

        shutil.move(str(temp_harness_dir), str(target_harness_dir))

        final_plugin_dir = target_harness_dir / "plugin-generated" if plugin_dir else None
        if final_plugin_dir:
            plugin_dir = str(final_plugin_dir)

        try:
            run_embedded_setup(
                Path(args.project_path),
                target_harness_dir,
                platform_choice,
                mcps_to_install,
                final_plugin_dir,
            )
        except HarnessSetupError as e:
            print(f"\n[HARNESS] ❌ ERROR: Embedded setup failed: {e}")
            langfuse_context.flush()
            sys.exit(1)

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
        print(f"\n   Routing rules in {harness_folder}/orchestrator.md have been updated.")
        
    print(f"\n{'='*60}\n")
    langfuse_context.flush()

if __name__ == "__main__":
    main()
