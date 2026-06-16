"""Reusable, side-effect-free render pipeline for the mint/update machinery.

This module is the SINGLE SOURCE OF TRUTH for the two-pass template render that
mint_workspace performs on each ``.md/.json/.yaml/.yml`` file (and on
``.env.telemetry-harness``).  ``minting_engine`` imports these symbols back so the
exact same transform is applied during both initial minting and later updates.

The render is intentionally a TWO-PASS pipeline:

* Pass 1 (:func:`render_pass1`): placeholder substitution + custom-delimiter
  Jinja rendering + tool-name replacements, applied to EVERY file.
* Pass 2 (:func:`process_includes`): ``@include`` inlining, which pulls in the
  content of sibling files *after* those siblings have themselves been through
  Pass 1.  Collapsing the two passes into one per-file call would inline
  not-yet-rendered content and change the deployed bytes — do not do it.

:func:`render_template` composes both passes for callers (the update machinery)
that operate on a single, already-rendered tree where same-pass ordering is not a
concern.

Quirks reproduced faithfully (intentionally NOT "fixed"):
  * the naive global ``".claude" -> target_dir_name`` ``str.replace``;
  * the ``"@boilerplate-agent" -> target_dir_name`` replace;
  * the SILENT ``try/except: pass`` around Jinja rendering (a stray ``<!--$`` in
    any file must not abort the render);
  * the tool_replacements ``str.replace`` pass.
"""

import os
from pathlib import Path

from jinja2 import Environment, BaseLoader


class TemplateRenderer:
    """Custom-delimiter Jinja renderer used by the harness templates.

    Delimiters are HTML-comment-like so raw template markers survive markdown
    tooling: blocks ``<!--% %-->``, variables ``<!--$ $-->``, comments
    ``<!--# #-->``.
    """

    def __init__(self):
        self.env = Environment(
            loader=BaseLoader(),
            block_start_string='<!--%',
            block_end_string='%-->',
            variable_start_string='<!--$',
            variable_end_string='$-->',
            comment_start_string='<!--#',
            comment_end_string='#-->',
        )

    def render_string(self, source: str, context: dict) -> str:
        template = self.env.from_string(source)
        return template.render(**context)


def process_includes(content: str, current_file_path: str, target_root: Path, tool_replacements: dict, target_dir_name: str, visited: set = None) -> str:
    """Recursively resolves @path includes at the start of lines, applying placeholders."""
    if visited is None:
        visited = set()

    lines = content.splitlines()
    new_lines = []

    for line in lines:
        if line.strip().startswith("@") and not line.strip().startswith("@ "):
            include_path_str = line.strip()[1:].strip()

            # Resolve the path relative to the current file
            current_dir = os.path.dirname(current_file_path)
            include_path = Path(os.path.normpath(os.path.join(current_dir, include_path_str)))

            abs_path_str = str(include_path.absolute())
            if abs_path_str in visited:
                print(f"Warning: Circular include detected for {include_path}")
                new_lines.append(line)
                continue

            if include_path.exists() and include_path.is_file():
                try:
                    with open(include_path, "r") as f:
                        include_content = f.read()

                    # Apply placeholders and tool mappings to the included content FIRST
                    include_content = include_content.replace(".claude", target_dir_name)
                    for old_tool, new_tool in tool_replacements.items():
                        include_content = include_content.replace(old_tool, new_tool)

                    visited.add(abs_path_str)
                    # Recursively process includes in the included file
                    resolved_content = process_includes(include_content, str(include_path), target_root, tool_replacements, target_dir_name, visited)
                    visited.remove(abs_path_str)
                    new_lines.append(resolved_content)
                except Exception as e:
                    print(f"Warning: Failed to inline {include_path}: {e}")
                    new_lines.append(line)
            else:
                # If it doesn't exist, maybe it's a subagent name like @agent
                # or it hasn't been minted yet. We leave it as is if it's not a valid file.
                new_lines.append(line)
        else:
            new_lines.append(line)

    return "\n".join(new_lines)


def render_pass1(content: str, *, target_dir_name: str, tool_replacements: dict, jinja_context: dict) -> str:
    """Apply the mint Pass-1 transform to a single file's content.

    This is the exact per-file transform from ``mint_workspace`` Step 1, MINUS
    the ``orchestrator.md``-only ``selected_agents`` injection (which is
    mint-specific and stays in the caller).

    Inputs:
      * ``content`` — raw file text.
      * ``target_dir_name`` — logical harness dir name that ``.claude`` /
        ``@boilerplate-agent`` placeholders resolve to.
      * ``tool_replacements`` — ``{old_tool: new_tool}`` literal substitutions.
      * ``jinja_context`` — the ``renderer_context`` dict passed to
        :class:`TemplateRenderer`.

    Output: the transformed text.

    Failure modes: Jinja rendering errors are swallowed SILENTLY (the Jinja step
    is a no-op pass-through when the source contains malformed template markers);
    placeholder and tool replacements always run regardless.
    """
    new_content = content

    # Naive placeholder substitutions (kept naive on purpose).
    new_content = new_content.replace(".claude", target_dir_name)
    if "@boilerplate-agent" in new_content:
        new_content = new_content.replace("@boilerplate-agent", target_dir_name)

    # Custom-delimiter Jinja render — SILENT on failure.
    try:
        new_content = TemplateRenderer().render_string(new_content, jinja_context)
    except Exception:
        # If rendering fails (e.g. a stray <!--$ in some file), leave the
        # post-placeholder content as-is and move on.
        pass

    # Tool-name replacements.
    for old_tool, new_tool in tool_replacements.items():
        new_content = new_content.replace(old_tool, new_tool)

    return new_content


def render_template(content: str, *, file_path: str, target_root: Path, target_dir_name: str, tool_replacements: dict, jinja_context: dict) -> str:
    """Full single-file render: :func:`render_pass1` then :func:`process_includes`.

    Intended for the update machinery, which renders an individual file against an
    already-rendered tree (so the cross-file Pass-1-before-Pass-2 ordering that
    mint must honour over the *whole* tree does not apply here).

    Inputs mirror :func:`render_pass1` plus:
      * ``file_path`` — path of the file being rendered (used to resolve
        ``@include`` paths relative to it).
      * ``target_root`` — root of the rendered tree (passed through to
        ``process_includes``).

    Output: fully rendered text with includes inlined.

    Tool-name mappings apply to PROSE surfaces only (.md/.json/.yaml — the
    same set mint renders).  Python source is exempt (Phase 6a, m3 risk class
    realized live): naive substring mapping turns ``.replace(`` method calls
    into ``.Edit(`` and collapses the deliberately cross-platform tool sets
    in hooks — deployed hooks handle every platform's tool names at runtime.
    """
    is_python = str(file_path).endswith(".py")
    effective_mappings = {} if is_python else tool_replacements
    rendered = render_pass1(
        content,
        target_dir_name=target_dir_name,
        tool_replacements=effective_mappings,
        jinja_context=jinja_context,
    )
    return process_includes(rendered, file_path, target_root, effective_mappings, target_dir_name)
