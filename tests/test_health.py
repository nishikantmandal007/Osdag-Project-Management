"""Tests for the board-health check.

``test_fresh_issue_is_not_flagged``
    The check must ignore young issues — flagging a day-old issue for having no
    owner turns the health report into noise and trains people to ignore it.

``test_stale_heartbeat_is_a_liveness_finding``
    The heartbeat exists to catch a *silently dead* reconciler. If a stale
    heartbeat did not surface, the one failure mode the whole mechanism is for
    would be invisible.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from pm.health import (
    check_health,
    heartbeat_age,
    write_health_report,
    HEALTH_REPORT,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _issue(number, days_old, labels=(), assignees=()):
    created = (NOW - timedelta(days=days_old)).isoformat()
    return {
        "number": number,
        "title": f"issue {number}",
        "html_url": f"http://x/{number}",
        "created_at": created,
        "labels": [{"name": n} for n in labels],
        "assignees": [{"login": a} for a in assignees],
    }


# ── heartbeat ────────────────────────────────────────────────────────────────

def test_heartbeat_age_fresh(tmp_path: Path):
    hb = tmp_path / ".heartbeat"
    hb.write_text((NOW - timedelta(hours=2)).isoformat() + "\n")
    age = heartbeat_age(NOW, hb)
    assert age is not None and age < timedelta(hours=3)


def test_heartbeat_age_missing_is_none(tmp_path: Path):
    assert heartbeat_age(NOW, tmp_path / "nope") is None


def test_missing_heartbeat_is_a_liveness_finding(tmp_path: Path):
    findings = check_health([], NOW, heartbeat_path=tmp_path / "nope")
    assert any(f.kind == "liveness" for f in findings)


def test_stale_heartbeat_is_a_liveness_finding(tmp_path: Path):
    hb = tmp_path / ".heartbeat"
    hb.write_text((NOW - timedelta(hours=50)).isoformat() + "\n")
    findings = check_health([], NOW, heartbeat_path=hb)
    live = [f for f in findings if f.kind == "liveness"]
    assert len(live) == 1 and "50h" in live[0].reasons[0]


def test_fresh_heartbeat_is_silent(tmp_path: Path):
    hb = tmp_path / ".heartbeat"
    hb.write_text((NOW - timedelta(hours=5)).isoformat() + "\n")
    findings = check_health([], NOW, heartbeat_path=hb)
    assert [f for f in findings if f.kind == "liveness"] == []


# ── hygiene ──────────────────────────────────────────────────────────────────

def _fresh_hb(tmp_path):
    hb = tmp_path / ".heartbeat"
    hb.write_text(NOW.isoformat() + "\n")
    return hb


def test_fresh_issue_is_not_flagged(tmp_path: Path):
    # 3 days old, no metadata at all — still in triage, must not be flagged.
    issues = [_issue(1, days_old=3)]
    findings = check_health(issues, NOW, heartbeat_path=_fresh_hb(tmp_path))
    assert [f for f in findings if f.kind == "hygiene"] == []


def test_stale_unowned_issue_is_flagged(tmp_path: Path):
    issues = [_issue(1, days_old=40, labels=["type:bug", "sev:S3-minor", "area:reports"])]
    findings = check_health(issues, NOW, heartbeat_path=_fresh_hb(tmp_path))
    hyg = [f for f in findings if f.kind == "hygiene"]
    assert len(hyg) == 1 and "no owner" in hyg[0].reasons and hyg[0].age_days == 40


def test_well_formed_stale_issue_is_clean(tmp_path: Path):
    issues = [_issue(1, days_old=40, labels=["type:task", "area:ci-cd"], assignees=["nishikant"])]
    findings = check_health(issues, NOW, heartbeat_path=_fresh_hb(tmp_path))
    assert [f for f in findings if f.kind == "hygiene"] == []


def test_bug_without_severity_is_flagged(tmp_path: Path):
    issues = [_issue(1, days_old=40, labels=["type:bug", "area:reports"], assignees=["x"])]
    findings = check_health(issues, NOW, heartbeat_path=_fresh_hb(tmp_path))
    hyg = [f for f in findings if f.kind == "hygiene"]
    assert len(hyg) == 1 and "bug without severity" in hyg[0].reasons


def test_epic_is_exempt(tmp_path: Path):
    # An old epic with no owner/severity is normal, not a finding.
    issues = [_issue(1, days_old=90, labels=["type:epic"])]
    findings = check_health(issues, NOW, heartbeat_path=_fresh_hb(tmp_path))
    assert [f for f in findings if f.kind == "hygiene"] == []


# ── report ───────────────────────────────────────────────────────────────────

def test_report_roundtrips(tmp_path: Path, monkeypatch):
    import pm.health as health
    monkeypatch.setattr(health, "HEALTH_REPORT", tmp_path / ".health-report.json")
    issues = [_issue(7, days_old=40, labels=["type:bug", "area:reports"])]
    findings = check_health(issues, NOW, heartbeat_path=_fresh_hb(tmp_path))
    write_health_report(findings, "o/n", NOW)
    import json
    data = json.loads((tmp_path / ".health-report.json").read_text())
    assert data["healthy"] is False
    assert data["stale_issues"][0]["number"] == 7
