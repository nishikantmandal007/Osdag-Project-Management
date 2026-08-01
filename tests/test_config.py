"""base + overlay merge is a lossless stand-in for the old monolithic config.

The point of the split is project-invariance without behaviour change: running
`--software osdagbridge` must reproduce today's labels, epics and board field/
view set exactly. These tests pin that by comparing the merged result against
the single-file loaders that still read the original `labels/epics/project.yml`.
When the monolithic files are retired, delete the equality tests and keep the
schema/overlay ones.
"""

from __future__ import annotations

import pytest

from pm.config import (
    ConfigError,
    list_software,
    load_epics,
    load_labels,
    load_merged,
    load_rollup,
)
from pm.project import load_project_config


# ── the split is lossless for OsdagBridge ────────────────────────────────────

def test_merged_labels_match_monolithic():
    """base.yml (type/sev) + osdagbridge.yml (area) == today's labels.yml."""
    merged = load_merged("osdagbridge").labels
    legacy = load_labels()

    assert merged.by_name() == legacy.by_name()
    assert merged.aliases() == legacy.aliases()
    assert merged.protected == legacy.protected
    assert merged.migrations == legacy.migrations


def test_merged_epics_match_monolithic():
    """osdagbridge.yml:epics == today's epics.yml, cross-checked vs merged labels."""
    merged = load_merged("osdagbridge")
    known = set(merged.labels.by_name())
    legacy = load_epics(known_labels=known)

    assert merged.epics.marker_prefix == legacy.marker_prefix
    assert merged.epics.epics == legacy.epics


def test_merged_board_reproduces_fields_and_views():
    """Derived Epic/Area options and shared fields/views reproduce project.yml.

    Field options are compared by (name, colour) — the functional contract the
    reconciler creates from. Option *descriptions* are cosmetic (never
    reconciled after a field is first created) and are intentionally derived
    from the single source (epic titles / area labels), so they are not asserted.
    """
    board = load_merged("osdagbridge").board
    legacy = load_project_config()

    assert board["project"] == legacy["project"]

    merged_fields = {f["name"]: f for f in board["fields"]}
    legacy_fields = {f["name"]: f for f in legacy["fields"]}
    assert list(merged_fields) == list(legacy_fields)  # same fields, same order

    for name, lf in legacy_fields.items():
        mf = merged_fields[name]
        assert mf["type"] == lf["type"], name
        if "options" in lf:
            merged_opts = [(o["name"], o.get("color")) for o in mf["options"]]
            legacy_opts = [(o["name"], o.get("color")) for o in lf["options"]]
            assert merged_opts == legacy_opts, name

    assert board["views"] == legacy["views"]


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
