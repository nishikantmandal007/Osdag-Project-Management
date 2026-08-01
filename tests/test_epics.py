"""Tests for the epics config and its idempotency marker.

``test_areas_must_be_real_labels``
    A typo'd area label would file an epic with a silently-missing tag. The
    loader must reject it against the known label set.

``test_marker_roundtrips``
    Idempotency hinges on the reconciler finding its own marker in a body it
    wrote. If the writer and the finder ever disagree, every re-run duplicates
    every epic. This pins them together.
"""

import pytest

from project_management.config import ConfigError, _epics_from_document, load_merged
from project_management.epics import MARKER_RE, _epic_body, _sub_body


def known_labels() -> set[str]:
    return set(load_merged("osdagbridge").labels.by_name()) | {"type:epic"}


def test_epics_config_loads_and_areas_exist():
    cfg = load_merged("osdagbridge").epics
    assert len(cfg.epics) == 10
    # E1 is the one that splits.
    e1 = next(e for e in cfg.epics if e.code.startswith("E1"))
    assert len(e1.sub_epics) == 6


def test_epic_codes_are_unique():
    cfg = load_merged("osdagbridge").epics
    codes = [e.code for e in cfg.epics]
    assert len(codes) == len(set(codes))


def test_areas_must_be_real_labels():
    bad = {
        "version": 1,
        "epics": [
            {
                "code": "E1 x",
                "title": "t",
                "outcome": "o",
                "release": "v1.0-GA",
                "areas": ["area:does-not-exist"],
            }
        ],
    }
    with pytest.raises(ConfigError, match="unknown area label"):
        _epics_from_document(bad, known_labels=known_labels())


@pytest.mark.parametrize(
    "key",
    ["E1 result-traceability", "E7 reporting-boq", "E1 result-traceability / shear"],
)
def test_marker_roundtrips(key):
    for body in (_epic_body("out", "v1.0-GA", "E1 result-traceability", key),
                 _sub_body("E1 result-traceability", key)):
        match = MARKER_RE.search(body)
        assert match is not None
        assert match.group(1).strip() == key
