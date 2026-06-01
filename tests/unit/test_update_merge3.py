"""A5 — real 3-way merge wrapper over `git merge-file` (not lossy section-union)."""
from harness.update.conflict import three_way


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
