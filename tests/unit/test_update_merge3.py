"""A5/C2 — real 3-way merge wrapper and conflict resolver."""

import pytest

from harness.update.conflict import (
    ConflictResolutionAborted,
    ConflictResolutionNeedsHuman,
    resolve,
    three_way,
)


def test_non_overlapping_changes_merge_clean():
    base = "line1\nline2\nline3\n"
    ours = "line1 MINE\nline2\nline3\n"      # edit first line
    theirs = "line1\nline2\nline3 THEIRS\n"  # edit last line
    merged, had_conflict = three_way(ours, base, theirs)
    assert had_conflict is False
    assert "line1 MINE" in merged
    assert "line3 THEIRS" in merged


def test_overlapping_changes_produce_conflict_markers():
    base = "shared\n"
    ours = "mine\n"
    theirs = "theirs\n"
    merged, had_conflict = three_way(ours, base, theirs)
    assert had_conflict is True
    assert "<<<<<<<" in merged and ">>>>>>>" in merged
    assert "mine" in merged and "theirs" in merged


def test_identical_sides_no_conflict():
    base = "a\nb\n"
    merged, had_conflict = three_way(base, base, base)
    assert had_conflict is False


def test_resolve_keep_returns_ours():
    result = resolve("file.txt", "base\n", "ours\n", "theirs\n", input_fn=lambda _: "K")
    assert result == "ours\n"


def test_resolve_overwrite_returns_theirs():
    result = resolve(
        "file.txt",
        "base\n",
        "ours\n",
        "theirs\n",
        input_fn=lambda _: "O",
    )
    assert result == "theirs\n"


def test_resolve_diff_shows_unified_diff_then_prompts_again():
    choices = iter(["D", "K"])
    output = []

    result = resolve(
        "file.txt",
        "base\n",
        "ours\n",
        "theirs\n",
        input_fn=lambda _: next(choices),
        output_fn=output.append,
    )

    assert result == "ours\n"
    assert "--- file.txt (ours)" in output[0]
    assert "+++ file.txt (theirs)" in output[0]
    assert "-ours" in output[0]
    assert "+theirs" in output[0]


def test_resolve_merge_clean_returns_merged_content():
    base = "line1\nline2\nline3\n"
    ours = "line1 MINE\nline2\nline3\n"
    theirs = "line1\nline2\nline3 THEIRS\n"

    result = resolve("file.txt", base, ours, theirs, input_fn=lambda _: "M")

    assert "line1 MINE" in result
    assert "line3 THEIRS" in result


def test_resolve_merge_conflict_opens_editor_and_returns_edited_content():
    def editor(path):
        assert "<<<<<<<" in path.read_text(encoding="utf-8")
        path.write_text("manual merge\n", encoding="utf-8")
        return 0

    result = resolve(
        "file.txt",
        "shared\n",
        "mine\n",
        "theirs\n",
        input_fn=lambda _: "M",
        editor=editor,
    )

    assert result == "manual merge\n"


def test_resolve_headless_signals_needs_human_without_prompting():
    def input_fn(prompt):
        raise AssertionError("headless resolver should not prompt")

    with pytest.raises(ConflictResolutionNeedsHuman):
        resolve("file.txt", "base\n", "ours\n", "theirs\n", headless=True, input_fn=input_fn)


@pytest.mark.parametrize("error", [EOFError, KeyboardInterrupt])
def test_resolve_input_abort_signals_clean_abort(error):
    with pytest.raises(ConflictResolutionAborted):
        resolve(
            "file.txt",
            "base\n",
            "ours\n",
            "theirs\n",
            input_fn=lambda _: (_ for _ in ()).throw(error()),
        )


def test_resolve_merge_conflict_missing_editor_reports_and_prompts_again(monkeypatch):
    monkeypatch.delenv("EDITOR", raising=False)
    choices = iter(["M", "K"])
    output = []

    result = resolve(
        "file.txt",
        "shared\n",
        "mine\n",
        "theirs\n",
        input_fn=lambda _: next(choices),
        output_fn=output.append,
    )

    assert result == "mine\n"
    assert output == ["Manual merge is unavailable because no editor is configured."]


def test_resolve_merge_conflict_invalid_editor_reports_and_prompts_again():
    choices = iter(["M", "K"])
    output = []

    result = resolve(
        "file.txt",
        "shared\n",
        "mine\n",
        "theirs\n",
        input_fn=lambda _: next(choices),
        editor="definitely-not-a-real-editor-command",
        output_fn=output.append,
    )

    assert result == "mine\n"
    assert output == ["Manual merge editor exited unsuccessfully."]


def test_resolve_merge_conflict_editor_keyboard_interrupt_aborts():
    def editor(path):
        raise KeyboardInterrupt

    with pytest.raises(ConflictResolutionAborted):
        resolve(
            "file.txt",
            "shared\n",
            "mine\n",
            "theirs\n",
            input_fn=lambda _: "M",
            editor=editor,
        )
