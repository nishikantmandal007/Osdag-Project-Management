"""The in-place board rename (Task #5 — suite rebrand).

`rename_project` is the one mutation that lets an overlay's `display_name`
change without bootstrap creating a second board: it moves the existing board
to the new title via `updateProjectV2`. These tests pin the mutation shape and
the fact that the merged config now declares the renamed title.
"""

from __future__ import annotations

from project_management.config import load_merged
from project_management.project import rename_project


class FakeGQL:
    """Records the last (query, variables) and returns a canned response."""

    def __init__(self, response: dict):
        self.response = response
        self.query: str | None = None
        self.variables: dict = {}

    def __call__(self, query: str, **variables):
        self.query = query
        self.variables = variables
        return self.response


def test_rename_project_sends_updateprojectv2_with_new_title():
    gql = FakeGQL(
        {"updateProjectV2": {"projectV2": {"id": "P_1", "number": 3, "title": "OsdagBridge"}}}
    )
    result = rename_project(gql, "P_1", "OsdagBridge")

    assert "updateProjectV2" in gql.query
    assert gql.variables == {"projectId": "P_1", "title": "OsdagBridge"}
    assert result["title"] == "OsdagBridge"


def test_overlay_declares_the_renamed_board_title():
    """The suite rebrand: board #3's title is the plain project name."""
    merged = load_merged("osdagbridge")
    assert merged.meta.display_name == "OsdagBridge"
    assert merged.board["project"]["title"] == "OsdagBridge"
