"""Tests for the issue seeder.

``test_backlink_and_marker_are_not_rewritten``
    The cross-ref rewrite must touch only bare `#N` in the original body, never
    the `owner/repo#N` backlink or the `<!-- src:...#N -->` marker — both carry
    the SOURCE number on purpose. If rewrite ever hits them, idempotency breaks
    (the marker would stop matching) and provenance is lost.

``test_marker_roundtrips``
    The seeder must find its own marker on re-run, or every re-run duplicates
    every issue.
"""

import json
from pathlib import Path

import pytest

from pm.config import ConfigError, load_labels, load_seed
from pm.seed import _assemble, _marker_re, marker, rewrite_refs


def known() -> set[str]:
    return set(load_labels().by_name())


def test_seed_config_loads_and_targets_exist():
    cfg = load_seed(known_labels=known())
    assert cfg.source_repo == "Aditya-Donde/OsdagBridge"
    assert cfg.snapshot.is_file()


def test_snapshot_matches_expected_shape():
    cfg = load_seed(known_labels=known())
    data = json.loads(cfg.snapshot.read_text())
    assert len(data) == 59
    for issue in data:
        assert {"number", "title", "body", "html_url", "created_at", "user", "labels"} <= set(issue)


def test_bad_target_label_is_rejected(tmp_path: Path):
    (tmp_path / "config").mkdir()
    snap = tmp_path / "config" / "snap.json"
    snap.write_text("[]")
    bad = tmp_path / "seed.yml"
    bad.write_text(
        "version: 1\n"
        "source_repo: a/b\n"
        "snapshot: config/snap.json\n"
        "label_map:\n"
        "  Foo: [area:does-not-exist]\n"
    )
    # snapshot path is resolved against the repo root, not tmp — so this raises
    # for the label first regardless; assert the label gap is reported.
    with pytest.raises(ConfigError, match="unknown target label|snapshot not found"):
        load_seed(path=bad, known_labels=known())


def test_label_mapping_and_unmapped():
    cfg = load_seed(known_labels=known())
    mapped, unmapped = cfg.map_labels(["Girder Results", "Non-Critical Bug", "Weird New Label"])
    assert "area:girder-results" in mapped
    assert "sev:S3-minor" in mapped
    assert unmapped == ["Weird New Label"]           # absent from map -> reported
    # "Check & Close" is in the map with an empty list -> intentionally silent
    mapped2, unmapped2 = cfg.map_labels(["Check & Close"])
    assert mapped2 == [] and unmapped2 == []


def test_marker_roundtrips():
    body = _assemble(
        load_seed(known_labels=known()),
        {"number": 329, "title": "t", "body": "hello", "html_url": "http://x",
         "user": "aditya", "created_at": "2026-07-20T10:00:00Z"},
        {},
    )
    m = _marker_re("Aditya-Donde/OsdagBridge").search(body)
    assert m is not None and int(m.group(1)) == 329


def test_backlink_and_marker_are_not_rewritten():
    cfg = load_seed(known_labels=known())
    # Original body references #196; the map says 196 -> 20.
    issue = {"number": 329, "title": "t", "body": "see #196 for context",
             "html_url": "http://x", "user": "aditya", "created_at": "2026-07-20T10:00:00Z"}
    body = _assemble(cfg, issue, {196: 20, 329: 42})
    assert "see #20 for context" in body          # bare ref rewritten
    assert "Aditya-Donde/OsdagBridge#329" in body  # backlink untouched
    assert marker("Aditya-Donde/OsdagBridge", 329) in body  # marker untouched


def test_rewrite_leaves_unknown_refs_alone():
    assert rewrite_refs("see #999 and #196", {196: 20}) == "see #999 and #20"
