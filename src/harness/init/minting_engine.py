import os
import re
import shutil
import json
import yaml
import urllib.request
import difflib
from pathlib import Path
from harness.init.plugin_generator import generate_orchestrator_plugin
from harness.adapters import get_adapter
# Single source of truth for the two-pass render. TemplateRenderer and
# process_includes were relocated to render.py; re-imported here to preserve the
# existing minting_engine.process_includes / .TemplateRenderer call sites.
from harness.init.render import (
    TemplateRenderer,
    process_includes,
    render_pass1,
    render_template,
)
from harness.init.runtime_slice import (
    RUNTIME_FILE_MAP,
    rewrite_imports,
    emit_platform_adapter,
)
from harness.init.rtk import RTK_RULES


def mint_workspace(target_dir: str, selected_agents: list[dict], project_path: str, platform_choice: str, model_choice: str = None, boilerplate_dir: str = None, logical_harness_name: str = None, enable_rtk: bool = False):
    """Copies boilerplate, injects styled configs, and writes setup prerequisites."""
    target_path = Path(target_dir)
    target_dir_name = logical_harness_name if logical_harness_name else target_path.name
    
    if target_path.exists():
        print(f"Warning: Target directory {target_dir} already exists. Minting may overwrite files.")
        
    def ignore_patterns(dir_path, contents):
        ignored = ['.git', '__pycache__', '.DS_Store', 'contracts', 'state']
        return [i for i in contents if i in ignored or i.endswith('.log')]
        
    if boilerplate_dir and os.path.exists(boilerplate_dir):
        shutil.copytree(boilerplate_dir, target_path, ignore=ignore_patterns, dirs_exist_ok=True)
        
        # Tool mapping for specific platforms
        platform_map_normalized = {"1": "gemini", "2": "claude", "3": "cursor", "4": "agents", "5": "codex"}
        current_platform = platform_map_normalized.get(platform_choice, platform_choice).lower()
        adapter = get_adapter(current_platform)
        
        # Cleanup files that are only used as source templates or specific to certain platforms
        readme_template_path = target_path / "README.md.template"
        if readme_template_path.exists():
            readme_template_path.unlink()
            
        onboarding_dir = target_path / "onboarding"
        if onboarding_dir.exists():
            shutil.rmtree(onboarding_dir)
            
        if current_platform != "claude":
            pyproject_path = target_path / "pyproject.toml"
            if pyproject_path.exists():
                pyproject_path.unlink()
        
        tool_replacements = adapter.get_tool_mappings()
        
        ingestion_key = os.environ.get("HARNESS_GLOBAL_INGESTION_BASE64", "YOUR_EMBEDDED_BASE64_STRING")
        project_slug = os.path.basename(os.path.abspath(project_path))
        
        renderer_context = {
            "HARNESS_DIR": target_dir_name,
            "subagent": adapter.get_subagent_text_call,
            "INGESTION_KEY": ingestion_key,
            "PROJECT_SLUG": project_slug
        }

        # Step 1: Apply placeholders and tool mappings to all files.
        # The placeholder + Jinja + tool-mapping transform is delegated to the
        # shared render_pass1 (single source of truth shared with the update
        # machinery). The orchestrator.md-only specialized-agents injection is
        # mint-specific and stays in this loop, applied after render_pass1.
        for root, _, files in os.walk(target_path):
            for file in files:
                if file.endswith((".md", ".json", ".yaml", ".yml")) or file == ".env.telemetry-harness":
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, "r") as f:
                            content = f.read()

                        new_content = render_pass1(
                            content,
                            target_dir_name=target_dir_name,
                            tool_replacements=tool_replacements,
                            jinja_context=renderer_context,
                        )

                        # Apply specialized agents injection to the active orchestrator surface.
                        if file == "orchestrator.md" and selected_agents:
                            agent_names = [agent['name'] for agent in selected_agents]
                            agents_str = ", ".join([f"`@{name}`" for name in agent_names])
                            injection = f"\n- **Domain Specific Routing**: If the task involves domain-specific areas similar to the domains defined by the newly minted specialized agents ({agents_str}), you MUST route to those agents. Refer to their markdown files in the agents directory for their specific mandates.\n"

                            # Inject right before the Negative Routing Rules section
                            if "**Negative Routing Rules" in new_content:
                                new_content = new_content.replace("**Negative Routing Rules", injection + "**Negative Routing Rules")

                        if new_content != content:
                            with open(filepath, "w") as f:
                                f.write(new_content)
                    except Exception as e:
                        print(f"Warning: Failed to process placeholders in {filepath}: {e}")

        # Step 2: Process @ includes (Inlining)
        # Now that all files have placeholders resolved, it's safe to inline them
        for root, _, files in os.walk(target_path):
            for file in files:
                if file.endswith((".md", ".json", ".yaml", ".yml")) or file == ".env.telemetry-harness":
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, "r") as f:
                            content = f.read()
                            
                        new_content = process_includes(content, filepath, target_path, tool_replacements, target_dir_name)
                            
                        if new_content != content:
                            with open(filepath, "w") as f:
                                f.write(new_content)
                    except Exception as e:
                        print(f"Warning: Failed to process includes in {filepath}: {e}")



        # Create the opt-in sentinel for the PostToolUse formatter hook.
        # Bootstrap projects get it automatically so formatting runs from day one.
        # Retrofit projects must add it manually after fixing pre-existing formatting.
        sentinel_path = target_path / ".harness-format-enabled"
        sentinel_path.parent.mkdir(parents=True, exist_ok=True)
        sentinel_path.touch()
        print(f"[HARNESS] Created formatter sentinel at {sentinel_path}")

    else:
        print("Error: Boilerplate directory not found.")
        return

    # Normalize platform choice
    platform_map = {
        "1": "gemini",
        "2": "claude",
        "3": "cursor",
        "4": "agents",
        "5": "codex"
    }
    active_platform = platform_map.get(platform_choice, platform_choice).lower()

    # Generate Platform Rules Pointers IN THE ROOT DIRECTORY
    adapter = get_adapter(active_platform)

    root_staging_dir = target_path / "root_staging"
    root_staging_dir.mkdir(parents=True, exist_ok=True)

    rules = [
        "**Graph-first:** Prefer the `codegraph` MCP (start with `codegraph_context`) over Grep/Glob/`find` for code search and navigation. Use text search only for non-indexed content (e.g. UI strings).",
        "**Project ops:** Before building, testing, or deploying, call the `domain` MCP's `domain_ops` tool (e.g. `domain_ops(\"deploy\")`) for THIS repo's real commands — stack, environments, test, deploy, infra, references — instead of guessing. For product/business judgment calls, consult `domain_ops(\"business\")`. Authored in the deployed `domain/domain.json`.",
    ]
    if enable_rtk:
        rules.append(RTK_RULES)
    injection_block = (
        "<!-- harness:start -->\n"
        + "\n\n".join(rules)
        + "\n<!-- harness:end -->"
    )

    files_to_generate = adapter.get_rules_pointer_files()
    project_root = Path(project_path)
    
    for rules_file in files_to_generate:
        existing_file_path = project_root / rules_file
        content = ""
        if existing_file_path.exists():
            try:
                with open(existing_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"Warning: Failed to read {existing_file_path}: {e}")
                
        pattern = r"<!-- harness:start -->.*?<!-- harness:end -->"
        if re.search(pattern, content, flags=re.DOTALL):
            new_content = re.sub(pattern, injection_block, content, flags=re.DOTALL)
        else:
            if content and not content.endswith('\n'):
                content += '\n'
            if content and not content.endswith('\n\n'):
                content += '\n'
            new_content = content + injection_block + "\n"

        staging_file_path = root_staging_dir / rules_file
        staging_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(staging_file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
    print(f"\nHarness files staged in {root_staging_dir}. They will be merged into the project root automatically.")

    # Helper to generate a valid URL-safe slug
    def to_slug(text):
        # 1. Handle CamelCase (Insert hyphens between lower-to-upper transitions)
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', text)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1-\2', s1).lower()
        # 2. Replace any non-alphanumeric character (except hyphens) with a hyphen
        s3 = re.sub(r'[^a-z0-9]+', '-', s2)
        # 3. Clean up multiple hyphens and leading/trailing
        return re.sub(r'-+', '-', s3).strip('-')

    # Generate Specialized Agents
    for agent in selected_agents:
        safe_name = to_slug(agent["name"])
        
        agent_dir_path = target_path / "agents"
        agent_dir_path.mkdir(parents=True, exist_ok=True)
        agent_file_path = agent_dir_path / f"{safe_name}.md" 
        
        # Select base tools based on platform
        if adapter.get_platform_name() == "claude":
            tools_list = """  - Read
  - Grep
  - Edit
  - Bash
  - Glob
  - mcp_codegraph_codegraph_search
  - mcp_codegraph_codegraph_node
  - mcp_codegraph_codegraph_context
  - mcp_codegraph_codegraph_callers
  - mcp_codegraph_codegraph_impact"""
        else:
            tools_list = """  - read_file
  - grep_search
  - replace
  - run_shell_command
  - glob
  - mcp_codegraph_codegraph_search
  - mcp_codegraph_codegraph_node
  - mcp_codegraph_codegraph_context
  - mcp_codegraph_codegraph_callers
  - mcp_codegraph_codegraph_impact"""
        
        frontmatter = f"""---
name: {safe_name}
description: {agent["role"]}
tools:
{tools_list}
---
"""
        system_prompt = agent.get("system_prompt", f"# {agent['name']}\n\n{agent['role']}")
        

        # Determine the correct include syntax based on platform
        include_pointer = ""
        if active_platform not in ["gemini", "claude", "cursor", "codex", "agents"]:
            # Fallback for cursor/agents where include syntax might not be natively supported
            include_pointer = "<!-- Core Mandates should be read from ../rules/base_mandate.md -->\n\n"

        final_content = frontmatter + include_pointer + system_prompt + "\n"
        
        # Final post-processing for placeholders and includes
        final_content = re.sub(r'(^|[\s/"\'])\.claude([\s/"\']|$)', r'\1' + target_dir_name + r'\2', final_content)
        final_content = process_includes(final_content, str(agent_file_path), target_path, tool_replacements, target_dir_name)
        
        with open(agent_file_path, 'w') as f:
            f.write(final_content)

    print(f"Successfully minted workspace at {target_dir}")
    print("\nNext Steps:")
    print("1. Activate your environment and Launch AI")
def perform_smart_merge(existing_path: Path, staged_path: Path):
    """
    Walks through staged_path and merges with existing_path if files exist there.
    Also preserves files from existing_path that are NOT in staged_path.
    """
    # 1. Merge existing files into staged
    for root, _, files in os.walk(staged_path):
        for file in files:
            staged_file = Path(root) / file
            rel_path = staged_file.relative_to(staged_path)
            existing_file = existing_path / rel_path
            
            if existing_file.exists() and existing_file.is_file():
                try:
                    with open(staged_file, 'r', encoding='utf-8') as f:
                        staged_content = f.read()
                    with open(existing_file, 'r', encoding='utf-8') as f:
                        existing_content = f.read()
                    
                    if file.endswith('.md'):
                        new_content = merge_markdown(existing_content, staged_content)
                    elif file.endswith(('.json', '.yaml', '.yml')):
                        fmt = 'json' if file.endswith('.json') else 'yaml'
                        new_content = merge_structured(existing_content, staged_content, format=fmt)
                    elif file.endswith(('.py', '.sh', '.js')):
                        new_content = handle_code_conflicts(existing_content, staged_content, str(rel_path))
                    else:
                        # For other files, treat as code for safety
                        new_content = handle_code_conflicts(existing_content, staged_content, str(rel_path))
                    
                    if new_content != staged_content:
                        with open(staged_file, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                except (UnicodeDecodeError, Exception) as e:
                    print(f"Skipping merge for {rel_path}: {e}")

    # 2. Preserve custom files from existing that are NOT in staged
    for root, _, files in os.walk(existing_path):
        for file in files:
            existing_file = Path(root) / file
            rel_path = existing_file.relative_to(existing_path)
            staged_file = staged_path / rel_path
            
            # Skip internal state files
            if "harness.db" in str(rel_path):
                continue
                
            if not staged_file.exists():
                # Ensure parent directory exists in staged
                staged_file.parent.mkdir(parents=True, exist_ok=True)
                # Copy file to staged
                shutil.copy2(existing_file, staged_file)
                print(f"[HARNESS] Preserved custom file: {rel_path}")

def handle_code_conflicts(old_content: str, new_content: str, file_path: str) -> str:
    """Handles conflicts in code files. In headless mode, auto-overwrites. Otherwise, prompts for manual resolution."""
    if old_content == new_content:
        return new_content

    # Headless mode check
    if os.environ.get("HARNESS_HEADLESS") == "1":
        print(f"[HARNESS] Headless mode: Auto-overwriting {file_path}")
        return new_content

    print(f"\n--- CONFLICT: {file_path} ---")
    import difflib
    diff = difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile="existing",
        tofile="minted"
    )
    print("".join(diff))
    
    while True:
        choice = input(f"Conflict in {file_path}. [O]verwrite with new version or [K]eep existing? ").strip().upper()
        if choice == 'O':
            return new_content
        elif choice == 'K':
            return old_content

def merge_markdown(old_content: str, new_content: str) -> str:
    """Merges two markdown files section by section based on headers."""
    def parse_sections(text):
        sections = {}
        # Find all headers and their positions
        header_iter = re.finditer(r'(?:^|\n)(#{1,6}\s+(.*))', text)
        headers = list(header_iter)
        
        if not headers:
            return {"__INTRO__": text.strip()}
            
        # Intro content before first header
        intro = text[:headers[0].start()].strip()
        if intro:
            sections["__INTRO__"] = intro
            
        for i in range(len(headers)):
            start = headers[i].start()
            end = headers[i+1].start() if i + 1 < len(headers) else len(text)
            
            full_section = text[start:end].strip()
            title = headers[i].group(1).strip()
            sections[title] = full_section
            
        return sections

    old_sections = parse_sections(old_content)
    new_sections = parse_sections(new_content)
    
    merged_sections = []
    
    # Capture intro if it exists in new, otherwise from old
    if "__INTRO__" in new_sections:
        merged_sections.append(new_sections["__INTRO__"])
    elif "__INTRO__" in old_sections:
        merged_sections.append(old_sections["__INTRO__"])
        
    # Add all new sections
    new_titles = [k for k in new_sections.keys() if k != "__INTRO__"]
    for title in new_titles:
        merged_sections.append(new_sections[title])
        
    # Add old sections that are NOT in new sections
    old_titles = [k for k in old_sections.keys() if k != "__INTRO__"]
    for title in old_titles:
        if title not in new_sections:
            merged_sections.append(old_sections[title])
            
    return "\n\n".join(merged_sections).strip()

def merge_structured(old_str: str, new_str: str, format: str = 'json') -> str:
    """Deep merges two JSON or YAML strings."""
    if format == 'json':
        try:
            old_data = json.loads(old_str)
        except json.JSONDecodeError:
            old_data = {}
        try:
            new_data = json.loads(new_str)
        except json.JSONDecodeError:
            new_data = {}
    else:
        try:
            old_data = yaml.safe_load(old_str) or {}
        except Exception:
            old_data = {}
        try:
            new_data = yaml.safe_load(new_str) or {}
        except Exception:
            new_data = {}
        
    merged = _deep_merge_logic(old_data, new_data)
    
    if format == 'json':
        return json.dumps(merged, indent=2)
    else:
        return yaml.dump(merged, sort_keys=False)

def _deep_merge_logic(base, update):
    """Internal recursive merge logic."""
    if isinstance(base, dict) and isinstance(update, dict):
        # We want to return a NEW dict, but update it
        res = base.copy()
        for k, v in update.items():
            if k in res:
                res[k] = _deep_merge_logic(res[k], v)
            else:
                res[k] = v
        return res
    elif isinstance(base, list) and isinstance(update, list):
        # For lists of dicts with a 'name' key, deduplicate by name (update wins).
        if all(isinstance(i, dict) and "name" in i for i in base + update):
            by_name = {i["name"]: i for i in base}
            for item in update:
                by_name[item["name"]] = item  # update overwrites same-named entry
            return list(by_name.values())
        # Plain lists: union without duplicates, preserving order
        res = list(base)
        for item in update:
            if item not in res:
                res.append(item)
        return res
    else:
        return update


def copy_runtime_modules(target_dir: Path, platform_id: str = "generic") -> None:
    """Copies runtime modules into the generated plugin's src/ directory.

    Ships a single canonical runtime slice (S2-T6):
      - runtime_adapter.py  — profile-driven adapter; provides get_adapter(platform).
      - profile.py          — typed profile accessor (stdlib-only, already standalone).
      - platform_profiles.json — platform data read by profile.py at runtime.
      - platform_adapter.py — EMITTED (not copied): a tiny no-arg shim that calls
        runtime_adapter.get_adapter("<platform_id>") with the platform baked in at
        mint time.  The prompt_classifier hook does ``from platform_adapter import
        get_adapter`` then ``adapter.format_hook_response(...)``.

    All copied .py files are rewritten to use flat local imports instead of
    harness.runtime.* / harness.init.* / harness.adapters.* paths, so the
    generated plugin runs without the harness package installed in the user's
    environment.

    The old per-platform standalone files (platform_adapter_claude.py, etc.) are
    NOT deleted here — that is deferred to S2-T7.

    Implementation delegates to the shared helpers in
    ``harness.init.runtime_slice`` (RUNTIME_FILE_MAP, rewrite_imports,
    emit_platform_adapter) — single source of truth for file list, regex, and
    emitted template (D4/D5).
    """
    package_root = Path(__file__).parent.parent  # src/harness/

    src_dir = target_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    for name, source_rel in RUNTIME_FILE_MAP.items():
        dest = src_dir / name

        if source_rel is None:
            # Emitted files
            if name == "platform_adapter.py":
                print(f"[HARNESS] Emitting platform_adapter.py (platform={platform_id!r})...")
                dest.write_text(emit_platform_adapter(platform_id), encoding="utf-8")
            elif name == "__init__.py":
                dest.write_text("")
            # (any future emitted sentinels land here as empty files)
        elif not name.endswith(".py"):
            # Verbatim non-Python copy (e.g. platform_profiles.json)
            src_path = package_root / source_rel
            if src_path.exists():
                print(f"[HARNESS] Copying {name} ({src_path.name})...")
                shutil.copy2(src_path, dest)
            else:
                print(f"[HARNESS] Warning: {name} not found at {src_path}")
        else:
            # Python source — copy then import-rewrite
            src_path = package_root / source_rel
            if src_path.exists():
                print(f"[HARNESS] Copying {name} ({src_path.name})...")
                text = src_path.read_text(encoding="utf-8")
                patched = rewrite_imports(text)
                dest.write_text(patched, encoding="utf-8")
            else:
                print(f"[HARNESS] Warning: {name} not found at {src_path}")
