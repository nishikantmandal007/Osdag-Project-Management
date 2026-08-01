"""Board-health check: surface what the board is quietly failing to track.

    python -m project_management.health --repo owner/name

Read-only over issue metadata (REST) plus the reconciler's heartbeat. Unlike the
label reconciler this is **not a gate** — stale issues are a normal fact of a
volunteer backlog, so it exits 0 and reports rather than failing CI. The nightly
opens a single "Board health" issue when there are findings and updates it in
place, so it informs without spamming.

Two independent signals:

* **Liveness** — the heartbeat is older than one nightly cycle, which means the
  reconciler itself may be silently dead. This is the finding that watches the
  watcher: config-drift detection is worthless if the job that runs it stopped
  months ago and nobody noticed. It is deliberately separate from drift — a
  heartbeat says *the automation executed*, drift says *the board matches config*.

* **Hygiene** — issues open past an age with no owner, no severity, or otherwise
  un-triaged. Only *old* issues are flagged: a day-old issue with no owner is in
  triage, not neglected.

**Documented limitation:** epic membership lives in a board *field*, not a label,
until the v2 ``epic:`` namespace ships. It cannot be read from issue metadata, so
"no epic" is not checked here even though the plan lists it. When ``epic:`` labels
exist this module gains one line; until then, claiming to check it would emit a
false finding on every issue.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .github import Client, GitHubError

HEARTBEAT = Path(".heartbeat")
HEALTH_REPORT = Path(".health-report.json")

# An issue younger than this is still moving through triage; nagging about it is
# noise. Past it, missing metadata is neglect worth surfacing.
STALE_DAYS = 30

# One nightly cycle is 24h; allow a generous margin for a late runner before
# calling the reconciler dead. Two missed nights is unambiguous.
MAX_HEARTBEAT = timedelta(hours=36)


@dataclass
class Finding:
    kind: str                       # "liveness" | "hygiene"
    reasons: list[str]
    number: int | None = None
    title: str = ""
    url: str = ""
    age_days: int | None = None

    def render(self) -> str:
        why = ", ".join(self.reasons)
        if self.number is None:
            return f"  [{self.kind}] {why}"
        return f"  #{self.number} ({self.age_days}d) — {why}: {self.title[:60]}"


def _parse_ts(text: str) -> datetime:
    """Parse an ISO timestamp, tolerating a trailing ``Z`` on 3.11 and 3.12."""
    return datetime.fromisoformat(text.strip().replace("Z", "+00:00"))


def heartbeat_age(now: datetime, path: Path = HEARTBEAT) -> timedelta | None:
    """Age of the last heartbeat, or ``None`` if it is missing or unreadable.

    A missing heartbeat is itself a liveness finding — the caller decides — so
    this returns ``None`` rather than raising.
    """
    try:
        stamp = _parse_ts(path.read_text())
    except (OSError, ValueError):
        return None
    return now - stamp


def _hygiene_reasons(issue: dict, now: datetime, stale_days: int) -> list[str]:
    """Metadata gaps for a single issue, empty if it is well-formed or too young.

    Gaps are only reported once the issue is stale; a fresh issue mid-triage is
    not a problem. Epics are exempt — they carry no severity or owner by nature.
    """
    labels = {lbl["name"] for lbl in issue.get("labels", [])}
    if "type:epic" in labels:
        return []

    created = _parse_ts(issue["created_at"])
    age = now - created
    if age.days <= stale_days:
        return []

    reasons: list[str] = []
    if not issue.get("assignees"):
        reasons.append("no owner")
    if not any(name.startswith("type:") for name in labels):
        reasons.append("no type")
    if not any(name.startswith("area:") for name in labels):
        reasons.append("no area")
    if "type:bug" in labels and not any(name.startswith("sev:") for name in labels):
        reasons.append("bug without severity")
    return reasons


def check_health(
    issues: list[dict],
    now: datetime,
    stale_days: int = STALE_DAYS,
    heartbeat_path: Path = HEARTBEAT,
    max_heartbeat: timedelta = MAX_HEARTBEAT,
) -> list[Finding]:
    """All findings, liveness first. ``issues`` should be the OPEN issues only."""
    findings: list[Finding] = []

    age = heartbeat_age(now, heartbeat_path)
    if age is None:
        findings.append(
            Finding("liveness", ["heartbeat missing — reconciler may never have run"])
        )
    elif age > max_heartbeat:
        hours = int(age.total_seconds() // 3600)
        findings.append(
            Finding(
                "liveness",
                [f"heartbeat is {hours}h old (> {int(max_heartbeat.total_seconds() // 3600)}h)"
                 " — the nightly reconciler has not run"],
            )
        )

    for issue in issues:
        reasons = _hygiene_reasons(issue, now, stale_days)
        if reasons:
            created = _parse_ts(issue["created_at"])
            findings.append(
                Finding(
                    "hygiene",
                    reasons,
                    number=issue["number"],
                    title=issue.get("title", ""),
                    url=issue.get("html_url", ""),
                    age_days=(now - created).days,
                )
            )
    return findings


def render(findings: list[Finding]) -> str:
    if not findings:
        return "board healthy: heartbeat fresh, no stale un-triaged issues."
    live = [f for f in findings if f.kind == "liveness"]
    hyg = [f for f in findings if f.kind == "hygiene"]
    lines: list[str] = []
    if live:
        lines.append(f"liveness: {len(live)} problem(s)")
        lines += [f.render() for f in live]
    if hyg:
        lines.append(f"\nhygiene: {len(hyg)} stale un-triaged issue(s) (> {STALE_DAYS}d)")
        lines += [f.render() for f in hyg]
    return "\n".join(lines)


def write_health_report(findings: list[Finding], repo: str, now: datetime) -> None:
    HEALTH_REPORT.write_text(
        json.dumps(
            {
                "repo": repo,
                "checked_at": now.isoformat(),
                "healthy": not findings,
                "liveness": [f.reasons for f in findings if f.kind == "liveness"],
                "stale_issues": [
                    {"number": f.number, "age_days": f.age_days, "reasons": f.reasons, "url": f.url}
                    for f in findings
                    if f.kind == "hygiene"
                ],
            },
            indent=2,
        )
        + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="project_management.health", description=__doc__)
    parser.add_argument("--repo", required=True, metavar="OWNER/NAME")
    parser.add_argument(
        "--stale-days", type=int, default=STALE_DAYS, help=f"age past which gaps matter (default {STALE_DAYS})"
    )
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="exit 1 if anything is flagged (default: report and exit 0)",
    )
    args = parser.parse_args(argv)

    # Heartbeat age is read BEFORE the reconciler overwrites it, so the nightly
    # must run this step first. Reading a just-written heartbeat would always
    # look fresh and the liveness check would be a no-op.
    now = datetime.now(timezone.utc)

    try:
        client = Client.from_env(args.repo)
        issues = client.list_issues(state="open")
    except GitHubError as exc:
        print(f"github error: {exc}", file=sys.stderr)
        return 2

    findings = check_health(issues, now, stale_days=args.stale_days)
    print(f"repo   : {args.repo}")
    print(f"open   : {len(issues)} issue(s)\n")
    print(render(findings))
    write_health_report(findings, args.repo, now)

    if findings and args.fail_on_findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
