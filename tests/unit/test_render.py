"""Characterization tests for the extracted render pipeline (render.py).

These pin the EXACT output of render_pass1 / render_template so the mint refactor
that routes through them cannot drift.  Each quirk required by the task is covered:
.claude placeholder, custom-delimiter Jinja var, tool-mapping replacement,
@include inlining, and silent pass-through of malformed Jinja.
"""

from pathlib import Path

import pytest

from harness.init.render import render_pass1, render_template, process_includes


# A representative renderer_context (mirrors mint's renderer_context dict).
JINJA_CTX = {
    "HARNESS_DIR": "my-harness",
    "subagent": "@",
    "INGESTION_KEY": "INGEST123",
    "PROJECT_SLUG": "my-project",
}


# --- render_pass1 -----------------------------------------------------------

def test_pass1_claude_placeholder_naive_global_replace():
    content = "See .claude/orchestrator.md and .claude.bak"
    out = render_pass1(
        content,
        target_dir_name="my-harness",
        tool_replacements={},
        jinja_context=JINJA_CTX,
    )
    # Naive global replace: EVERY ".claude" becomes the dir name, including
    # ".claude.bak" -> "my-harness.bak".
    assert out == "See my-harness/orchestrator.md and my-harness.bak"


def test_pass1_boilerplate_agent_replace():
    content = "Route to @boilerplate-agent now"
    out = render_pass1(
        content,
        target_dir_name="my-harness",
        tool_replacements={},
        jinja_context=JINJA_CTX,
    )
    assert out == "Route to my-harness now"


def test_pass1_jinja_variable_rendered():
    content = "Harness dir is <!--$ HARNESS_DIR $--> and key <!--$ INGESTION_KEY $-->."
    out = render_pass1(
        content,
        target_dir_name="my-harness",
        tool_replacements={},
        jinja_context=JINJA_CTX,
    )
    assert out == "Harness dir is my-harness and key INGEST123."


def test_pass1_tool_replacement():
    content = "Use Read and Grep tools."
    out = render_pass1(
        content,
        target_dir_name="my-harness",
        tool_replacements={"Read": "read_file", "Grep": "grep_search"},
        jinja_context=JINJA_CTX,
    )
    assert out == "Use read_file and grep_search tools."


def test_pass1_malformed_jinja_passes_through_silently_after_placeholders():
    # A stray, unclosed variable marker is invalid Jinja. The Jinja step must
    # fail SILENTLY, leaving the post-placeholder content intact (placeholders
    # and tool replacements still applied around the swallowed error).
    content = "Broken <!--$ HARNESS_DIR  marker for .claude with Read"
    out = render_pass1(
        content,
        target_dir_name="my-harness",
        tool_replacements={"Read": "read_file"},
        jinja_context=JINJA_CTX,
    )
    # .claude -> my-harness happened (pre-Jinja), Jinja swallowed, Read -> read_file
    # happened (post-Jinja). The malformed marker survives verbatim.
    assert out == "Broken <!--$ HARNESS_DIR  marker for my-harness with read_file"


def test_pass1_ordering_placeholder_before_jinja():
    # ".claude" substitution runs BEFORE Jinja, so a jinja var feeding off the
    # dir name is unaffected; this pins the documented order.
    content = ".claude :: <!--$ HARNESS_DIR $-->"
    out = render_pass1(
        content,
        target_dir_name="dir-x",
        tool_replacements={},
        jinja_context={"HARNESS_DIR": "dir-x"},
    )
    assert out == "dir-x :: dir-x"


# --- render_template (pass1 + includes) -------------------------------------

def test_render_template_inlines_include(tmp_path):
    # Sibling file that will be inlined. process_includes applies .claude +
    # tool replacements to included content itself.
    included = tmp_path / "snippet.md"
    included.write_text("Included body referencing .claude and Read")

    main = tmp_path / "main.md"
    main_content = "Header for <!--$ HARNESS_DIR $-->\n@snippet.md\nFooter"

    out = render_template(
        main_content,
        file_path=str(main),
        target_root=tmp_path,
        target_dir_name="my-harness",
        tool_replacements={"Read": "read_file"},
        jinja_context=JINJA_CTX,
    )

    expected = (
        "Header for my-harness\n"
        "Included body referencing my-harness and read_file\n"
        "Footer"
    )
    assert out == expected


def test_render_template_missing_include_left_verbatim(tmp_path):
    main = tmp_path / "main.md"
    main_content = "Top\n@does-not-exist.md\nBottom for .claude"

    out = render_template(
        main_content,
        file_path=str(main),
        target_root=tmp_path,
        target_dir_name="my-harness",
        tool_replacements={},
        jinja_context=JINJA_CTX,
    )
    # Pass1 replaced .claude; the unresolved @include line stays as-is.
    assert out == "Top\n@does-not-exist.md\nBottom for my-harness"


def test_render_template_equals_pass1_then_process_includes(tmp_path):
    # Belt-and-suspenders: render_template must equal the manual composition,
    # proving it is a faithful, side-effect-free composition of the two passes.
    included = tmp_path / "inc.md"
    included.write_text("inc .claude")
    main = tmp_path / "m.md"
    main_content = "x <!--$ HARNESS_DIR $-->\n@inc.md"

    via_template = render_template(
        main_content,
        file_path=str(main),
        target_root=tmp_path,
        target_dir_name="dir-z",
        tool_replacements={},
        jinja_context={"HARNESS_DIR": "dir-z"},
    )
    manual_p1 = render_pass1(
        main_content,
        target_dir_name="dir-z",
        tool_replacements={},
        jinja_context={"HARNESS_DIR": "dir-z"},
    )
    manual = process_includes(manual_p1, str(main), tmp_path, {}, "dir-z")
    assert via_template == manual
