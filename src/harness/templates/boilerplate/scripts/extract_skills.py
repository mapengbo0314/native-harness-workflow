#!/usr/bin/env python3
"""extract_skills.py — Continuous Learning skill extraction.

Reads session transcript, calls the LLM runtime client to extract learned engineering
skills/instincts, formats them with metadata (slug, confidence, stack, business),
writes them to out-of-repo projects storage, dedups against existing skills, and
cleans up lockfiles/input files on completion.

Fail-open: logs error and exits 0 on any exception.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

# Try importing query_llm from multiple possible locations to support both
# testing inside the harness repo and production inside the minted plugin.
try:
    from harness.runtime.llm_client import query_llm
except ImportError:
    try:
        from llm_client import query_llm
    except ImportError:
        def query_llm(prompt: str, cli_name: str, model: str = None) -> str:
            raise RuntimeError("LLM runtime client not found.")


def get_repo_hash(project_root: Path) -> str:
    """Compute a deterministic 16-character sha256 hash of the resolved project root."""
    path_str = str(project_root.resolve())
    return hashlib.sha256(path_str.encode("utf-8")).hexdigest()[:16]


def parse_frontmatter(content: str) -> dict:
    """Parse YAML-like frontmatter from a markdown string robustly.
    Splits on the first colon, strips surrounding quotes, whitespace and comments.
    """
    frontmatter = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            for line in fm_text.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip()
                    if k.startswith("'") and k.endswith("'"):
                        k = k[1:-1].strip()
                    if k.startswith('"') and k.endswith('"'):
                        k = k[1:-1].strip()
                    
                    v = v.strip()
                    # Strip inline comments starting with #
                    if "#" in v:
                        v = v.split("#", 1)[0].strip()
                    if v.startswith("'") and v.endswith("'"):
                        v = v[1:-1].strip()
                    if v.startswith('"') and v.endswith('"'):
                        v = v[1:-1].strip()
                    
                    # Parse simple lists or floats
                    if v.startswith("[") and v.endswith("]"):
                        try:
                            import ast
                            v = ast.literal_eval(v)
                        except Exception:
                            pass
                    else:
                        try:
                            v = float(v)
                        except ValueError:
                            pass
                    frontmatter[k] = v
    return frontmatter


def extract_and_save(plugin_root: Path, input_file: Path, session_id: str) -> None:
    """Perform the skill extraction workflow and ensure clean exit/cleanup."""
    plugin_root = Path(plugin_root).resolve()
    input_file = Path(input_file).resolve()
    state_dir = plugin_root / "state"
    lockfile = state_dir / "learning.lock"

    try:
        # 1. Read input payload
        if not input_file.exists():
            return

        try:
            payload = json.loads(input_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[Continuous Learning] Failed to load input JSON: {e}")
            return

        # 2. Get workspace root and transcript
        workspace_root_str = payload.get("workspace_root")
        if not workspace_root_str:
            workspace_root_str = str(plugin_root.parent)
        workspace_root = Path(workspace_root_str).resolve()

        transcript = payload.get("transcript") or payload.get("turns") or []
        if not isinstance(transcript, list) or not transcript:
            return

        # 3. Format transcript for LLM
        transcript_lines = []
        for turn in transcript:
            role = turn.get("role") or "unknown"
            text = turn.get("text") or ""
            # Cap long turns to avoid overflowing LLM limits
            if len(text) > 2000:
                text = text[:1997] + "..."
            transcript_lines.append(f"{role.upper()}: {text}")

        transcript_text = "\n".join(transcript_lines)

        # 4. Determine platform CLI name
        cli_name = os.environ.get("HARNESS_PLATFORM_CLI")
        if not cli_name:
            if "CLAUDE_PLUGIN_ROOT" in os.environ or "CLAUDE_SESSION_ID" in os.environ:
                cli_name = "claude"
            else:
                cli_name = "gemini"

        # 5. Formulate prompt
        prompt = f"""You are the Continuous Learning extraction agent.
Analyze the following session transcript of an engineering agent interacting with a user and a codebase.
Identify any unique engineering skill, technique, codebase pattern, or problem-solving behavior learned during this session.

The skill must be concrete, specific, and actionable. Do not extract general concepts like "how to write python".
Instead, extract specific codebase design choices, custom library usages, domain rules, or complex debug patterns.

You MUST return a JSON object with the following fields:
1. "slug": a unique slug for the skill, e.g., "optimize-postgres-indexing".
2. "title": a human-readable title for the skill.
3. "description": a short description (under 220 characters).
4. "confidence": a confidence score between 0.3 and 0.9 representing how clearly the skill was demonstrated/validated.
5. "stack": a list of technologies involved, e.g., ["python", "postgres"].
6. "business": a list of business domains involved, e.g., ["payment-processing"].
7. "content": a detailed Markdown body describing the skill, why/when to use it, the steps, and code examples.

JSON schema:
{{
  "slug": "string (slug format)",
  "title": "string",
  "description": "string (< 220 chars)",
  "confidence": float (between 0.3 and 0.9),
  "stack": ["string", ...],
  "business": ["string", ...],
  "content": "string (markdown content)"
}}

Only output valid JSON. No other text.

Transcript:
{transcript_text}
"""

        # 6. Query the LLM
        # Set recursion guard before calling query_llm
        os.environ["HARNESS_INTERNAL_LLM_CALL"] = "1"
        try:
            response_text = query_llm(prompt, cli_name)
        except Exception as e:
            print(f"[Continuous Learning] LLM query failed: {e}")
            return

        # Parse LLM response JSON
        try:
            # Clean up potential markdown formatting from LLM response if present
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text.split("```json", 1)[1]
            if response_text.endswith("```"):
                response_text = response_text.rsplit("```", 1)[0]
            response_text = response_text.strip()

            skill_data = json.loads(response_text)
        except Exception as e:
            print(f"[Continuous Learning] Failed to parse LLM response JSON: {e}")
            return

        # 7. Validate and extract fields with defaults
        slug = skill_data.get("slug")
        if not slug or not isinstance(slug, str):
            return
        slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in slug).lower().strip("-_")

        description = skill_data.get("description") or "Learned codebase skill."
        if len(description) > 220:
            description = description[:217] + "..."

        try:
            confidence = float(skill_data.get("confidence") or 0.5)
            confidence = max(0.3, min(0.9, confidence))
        except ValueError:
            confidence = 0.5

        stack = skill_data.get("stack") or []
        if not isinstance(stack, list):
            stack = [str(stack)]
        stack = [str(s) for s in stack]

        business = skill_data.get("business") or []
        if not isinstance(business, list):
            business = [str(business)]
        business = [str(b) for b in business]

        content = skill_data.get("content") or "No detailed description provided."

        # 8. Resolve out-of-repo learned storage path
        # Check environment variable override for isolated testing
        home_dir_str = os.environ.get("HARNESS_HOME_OVERRIDE")
        if home_dir_str:
            home_dir = Path(home_dir_str).resolve()
        else:
            home_dir = Path.home().resolve()

        repo_hash = get_repo_hash(workspace_root)
        learned_dir = home_dir / ".local" / "share" / "harness-wf" / "projects" / repo_hash / "learned"
        skill_dir = learned_dir / slug
        skill_file = skill_dir / "SKILL.md"

                # 9. Dedup check: Compare confidence against existing skill
        if skill_file.exists():
            try:
                existing_content = skill_file.read_text(encoding="utf-8")
                existing_fm = parse_frontmatter(existing_content)
                try:
                    conf_val = existing_fm.get("confidence", "0.0")
                    if isinstance(conf_val, str):
                        conf_val = conf_val.strip()
                        if "#" in conf_val:
                            conf_val = conf_val.split("#", 1)[0].strip()
                        if conf_val.startswith("'") and conf_val.endswith("'"):
                            conf_val = conf_val[1:-1].strip()
                        if conf_val.startswith('"') and conf_val.endswith('"'):
                            conf_val = conf_val[1:-1].strip()
                    existing_confidence = float(conf_val)
                except ValueError as e:
                    print(f"[Continuous Learning] Warning: failed to parse confidence value {existing_fm.get('confidence')}: {e}", file=sys.stderr)
                    existing_confidence = 0.0
                if confidence <= existing_confidence:
                    print(f"[Continuous Learning] Kept existing skill '{slug}' with higher confidence {existing_confidence} >= {confidence}")
                    return
            except Exception as e:
                print(f"[Continuous Learning] Error during dedup check: {e}")

# 10. Format and write SKILL.md
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_md = f"""---
name: {slug}
description: {description}
confidence: {confidence}
stack: {stack}
business: {business}
---

{content}
"""
        skill_file.write_text(skill_md, encoding="utf-8")
        print(f"[Continuous Learning] Successfully saved learned skill: {slug}")

    except Exception as e:
        print(f"[Continuous Learning] Unhandled exception: {e}")
    finally:
        # Always clean up the lockfile and the input payload file on exit
        try:
            if input_file.exists():
                input_file.unlink()
        except Exception:
            pass
        try:
            if lockfile.exists():
                lockfile.unlink()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract skills from session transcript.")
    parser.add_argument("--plugin-root", required=True, help="Path to plugin root.")
    parser.add_argument("--input-file", required=True, help="Path to input JSON payload.")
    parser.add_argument("--session-id", required=True, help="Session identifier.")
    args = parser.parse_args()

    # Fail-open execution: logs any unhandled error but exits 0
    try:
        extract_and_save(
            plugin_root=Path(args.plugin_root),
            input_file=Path(args.input_file),
            session_id=args.session_id,
        )
    except Exception as e:
        print(f"[Continuous Learning] Script execution error: {e}")
        sys.exit(0)


if __name__ == "__main__":
    main()
