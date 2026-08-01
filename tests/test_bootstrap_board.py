"""The board builder's config-side helpers (no network).

``_apply_sprint_start`` is what lets a demo board's first sprint begin on the day
it is stood up. It only moves where the numbering starts; sprint *length* is the
config's, untouched. These pin the date handling and the two failure modes so a
typo can never silently leave the frozen base.yml date in a live demo board.
"""

from __future__ import annotations

import copy
from datetime import date

import pytest

from project_management.bootstrap_board import _apply_sprint_start
from project_management.config import load_merged
from project_management.project import ProjectError


def _board():
    return copy.deepcopy(load_merged("osdagbridge").board)


def _sprint(board):
    return next(f for f in board["fields"] if f.get("type") == "ITERATION")


def test_explicit_date_sets_sprint_start():
    board = _board()
    resolved = _apply_sprint_start(board, "2026-09-07")
    assert resolved == "2026-09-07"
    assert _sprint(board)["start_date"] == "2026-09-07"


def test_today_resolves_to_current_date():
    board = _board()
    resolved = _apply_sprint_start(board, "today")
    assert resolved == date.today().isoformat()
    assert _sprint(board)["start_date"] == resolved


def test_length_is_untouched():
    """Moving the start must not change duration — only where numbering begins."""
    board = _board()
    before = _sprint(board)["duration_days"]
    _apply_sprint_start(board, "today")
    assert _sprint(board)["duration_days"] == before


def test_malformed_date_is_a_readable_error():
    with pytest.raises(ProjectError, match="YYYY-MM-DD or 'today'"):
        _apply_sprint_start(_board(), "next monday")


def test_board_without_iteration_is_rejected():
    board = _board()
    board["fields"] = [f for f in board["fields"] if f.get("type") != "ITERATION"]
    with pytest.raises(ProjectError, match="no ITERATION"):
        _apply_sprint_start(board, "today")
