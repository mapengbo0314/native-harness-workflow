"""Pin the single platform digit→name/folder map (review 2026-06-12 H4).

Before this, the ``{"1":"gemini",...}`` map was hand-duplicated 3× plus a 4th
if/elif folder map. These tests lock the behavior of the shared helpers so the
de-duplication is provably equivalent to the originals.
"""
from __future__ import annotations

import pytest

from harness.init.platforms import (
    PLATFORM_BY_DIGIT,
    platform_name_from_choice,
    harness_folder_from_choice,
)


@pytest.mark.parametrize(
    "choice,name",
    [("1", "gemini"), ("2", "claude"), ("3", "cursor"), ("4", "agents"), ("5", "codex")],
)
def test_digit_maps_to_canonical_name(choice, name):
    assert platform_name_from_choice(choice) == name


def test_unknown_choice_passes_through_lowercased():
    assert platform_name_from_choice("Claude") == "claude"
    assert platform_name_from_choice("9") == "9"


@pytest.mark.parametrize(
    "choice,folder",
    [
        ("1", ".gemini"),
        ("2", ".claude"),
        ("3", ".cursor"),
        ("4", ".agents"),
        ("5", ".codex"),
    ],
)
def test_folder_matches_legacy_if_elif(choice, folder):
    assert harness_folder_from_choice(choice) == folder


def test_unknown_choice_folder_falls_back_to_agents():
    # Legacy if/elif sent anything not 1/2/3/5 to ".agents".
    assert harness_folder_from_choice("9") == ".agents"
    assert harness_folder_from_choice("") == ".agents"


def test_map_is_the_single_source_used_by_callers():
    from harness.init import cli, minting_engine

    assert cli.platform_name_from_choice is platform_name_from_choice
    assert minting_engine.platform_name_from_choice is platform_name_from_choice
    assert set(PLATFORM_BY_DIGIT) == {"1", "2", "3", "4", "5"}
