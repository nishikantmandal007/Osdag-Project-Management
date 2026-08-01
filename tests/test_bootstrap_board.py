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

from project_management.bootstrap_board import (
    _apply_sprint_start,
    _merge_options,
    _options_in_sync,
)
from project_management.config import load_merged
from project_management.project import ProjectError

# GitHub ships every new board this built-in Status field.
GITHUB_DEFAULT_STATUS = [
    {"id": "1", "name": "Todo", "color": "GRAY", "description": ""},
    {"id": "2", "name": "In Progress", "color": "YELLOW", "description": ""},
    {"id": "3", "name": "Done", "color": "GREEN", "description": ""},
]


def _status_options():
    board = load_merged("osdagbridge").board
    status = next(f for f in board["fields"] if f["name"] == "Status")
    return status["options"]


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


# ── single-select option reconcile (the built-in Status fix) ─────────────────

def test_merge_adds_configured_status_flow_onto_github_default():
    """The whole point: our 9-state flow must land on the built-in Status field,
    which ships with only Todo/In Progress/Done."""
    config = _status_options()
    merged, added, preserved = _merge_options(config, GITHUB_DEFAULT_STATUS)

    names = [m["name"] for m in merged]
    # Every configured option is present, in config order, first.
    assert names[: len(config)] == [o["name"] for o in config]
    assert "Live in Dev" in names and "Triage" in names
    # The new columns are reported as added; the two GitHub defaults that match a
    # config name by (In Progress, Done) are not re-added.
    assert "In Progress" not in added and "Done" not in added
    assert "Backlog" in added and "Live in Dev" in added


def test_merge_preserves_unconfigured_option_never_deletes():
    """GitHub's 'Todo' isn't in our config; it must be carried through, not
    dropped — the never-delete invariant."""
    merged, added, preserved = _merge_options(_status_options(), GITHUB_DEFAULT_STATUS)
    assert preserved == ["Todo"]
    assert merged[-1]["name"] == "Todo"  # extras appended, after the config flow


def test_merge_options_carry_color_and_description():
    """Options sent to the API must have non-null color and description."""
    merged, _, _ = _merge_options(_status_options(), GITHUB_DEFAULT_STATUS)
    for opt in merged:
        assert set(opt) == {"name", "color", "description"}
        assert opt["color"] and opt["description"] is not None


def test_reconcile_is_idempotent_after_first_apply():
    """First apply changes the field; a second run over the resulting options
    must report in-sync so bootstrap stays a no-op."""
    config = _status_options()
    merged, _, _ = _merge_options(config, GITHUB_DEFAULT_STATUS)
    # Simulate the live field after the update stored exactly `merged`.
    live_after = [dict(m, id=str(i)) for i, m in enumerate(merged)]

    remerged, added, preserved = _merge_options(config, live_after)
    assert added == []                       # nothing new to add
    assert preserved == ["Todo"]             # Todo still preserved, not re-dropped
    assert _options_in_sync(remerged, live_after)  # → bootstrap skips the update


def test_out_of_sync_when_config_options_missing():
    """A field still on GitHub's defaults is out of sync → triggers an update."""
    config = _status_options()
    merged, _, _ = _merge_options(config, GITHUB_DEFAULT_STATUS)
    assert not _options_in_sync(merged, GITHUB_DEFAULT_STATUS)
