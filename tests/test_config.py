"""base + overlay merge builds each project's board from a shared half.

One engine runs several FOSSEE-project boards. `config/base.yml` holds what is
identical across them; `config/software/<name>.yml` holds what differs.
`load_merged(name)` stitches the two into the label / epic / board shapes the
reconciler consumes. These tests pin that the merge is well-formed, that the
OsdagBridge board carries every field and view it is supposed to, and that a
second project (Osdag) is genuinely independent.
"""

from __future__ import annotations

import pytest

from project_management.config import (
    ConfigError,
    list_software,
    load_merged,
    load_rollup,
)


# ── the OsdagBridge board is complete ────────────────────────────────────────

# The fields and views the merged board must expose, in order. Base supplies
# most; the Epic and Area fields are derived from the overlay. Kept here as the
# explicit contract the reconciler builds from — a dropped field would silently
# discard every value set on it, so this list is deliberately spelled out.
EXPECTED_FIELDS = [
    "Status", "Sprint", "Priority", "Severity", "Size", "Points",
    "Epic", "Area", "Target release", "Deploy stage", "Start date", "Target date",
]
EXPECTED_VIEWS = [
    "Current Sprint", "Triage Queue", "Backlog Grooming", "Epic Roadmap",
    "Release v1.0-GA", "By Owner", "Release pipeline", "Workload",
]


def test_merged_board_has_expected_fields_and_views():
    """The board carries every field and view, in order, titled 'OsdagBridge'."""
    board = load_merged("osdagbridge").board

    assert board["project"]["title"] == "OsdagBridge"
    assert board["project"]["short_description"]

    assert [f["name"] for f in board["fields"]] == EXPECTED_FIELDS
    assert [v["name"] for v in board["views"]] == EXPECTED_VIEWS


def test_deploy_stage_field_and_merged_status_and_release_view():
    """Task #6 additions: release-lifecycle axis separate from the dev flow."""
    board = load_merged("osdagbridge").board

    status = next(f for f in board["fields"] if f["name"] == "Status")
    assert "Merged" in [o["name"] for o in status["options"]]

    deploy = next(f for f in board["fields"] if f["name"] == "Deploy stage")
    assert deploy["type"] == "SINGLE_SELECT"
    assert [o["name"] for o in deploy["options"]] == [
        "Dev", "Test", "Ready for Prod", "In Production",
    ]

    assert "Release pipeline" in [v["name"] for v in board["views"]]


def test_merged_epic_field_options_are_the_epic_codes():
    """The Epic board field is derived from the epics, not written twice."""
    merged = load_merged("osdagbridge")
    epic_field = next(f for f in merged.board["fields"] if f["name"] == "Epic")
    option_names = [o["name"] for o in epic_field["options"]]
    assert option_names == [e.code for e in merged.epics.epics]


def test_merged_area_options_ui_purple_code_blue():
    """UI areas (with an alias) are purple; code areas are blue."""
    board = load_merged("osdagbridge").board
    area_field = next(f for f in board["fields"] if f["name"] == "Area")
    by_name = {o["name"]: o["color"] for o in area_field["options"]}
    assert by_name["girder-results"] == "PURPLE"   # UI (alias)
    assert by_name["design-core"] == "BLUE"        # code-side


# ── every overlay is valid, and a second project is genuinely independent ─────

def test_all_overlays_load():
    """Every config/software/*.yml validates and merges without error."""
    names = list_software()
    assert "osdagbridge" in names and "osdag" in names
    for name in names:
        merged = load_merged(name)
        assert merged.meta.name == name
        assert merged.meta.source_repos
        assert merged.epics.epics


def test_second_project_is_independent():
    """Osdag's areas/epics are its own, not OsdagBridge's — proves invariance."""
    osdag = load_merged("osdag")
    bridge = load_merged("osdagbridge")

    assert osdag.meta.display_name != bridge.meta.display_name
    assert set(osdag.labels.by_name()) != set(bridge.labels.by_name())
    # The shared type/sev namespaces ARE identical across projects.
    shared = {n for n in osdag.labels.by_name() if n.startswith(("type:", "sev:"))}
    assert shared == {n for n in bridge.labels.by_name() if n.startswith(("type:", "sev:"))}


# ── failure modes ────────────────────────────────────────────────────────────

def test_unknown_software_is_a_readable_error():
    with pytest.raises(ConfigError) as exc:
        load_merged("does-not-exist")
    assert "no overlay" in str(exc.value)


def test_rollup_lists_only_real_projects():
    """rollup.yml's Software options must each have an overlay."""
    document = load_rollup()
    available = set(list_software())
    assert set(document["software"]) <= available
    assert document["software_field"]["name"] == "Software"
