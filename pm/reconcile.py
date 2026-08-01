"""Make each of a project's source repos match `config/`.

    python -m pm.reconcile --software osdagbridge --dry-run
    python -m pm.reconcile --software osdagbridge --apply
    python -m pm.reconcile --software osdagbridge --repo owner/name   # one repo

The label set comes from ``--software`` (base.yml + the overlay). The *targets*
are the overlay's ``source_repos`` — labels-as-code lives on the real issues, in
place, not on a mirror. ``--repo`` overrides that to reconcile a single repo (for
example the PM repo's own process labels).

Defaults to ``--dry-run``: you have to ask for mutations explicitly. Exit codes
are chosen so CI can use this directly:

    0  every target matches config (extras may still be reported)
    1  drift found in --dry-run, or a run failed
    2  config is invalid — nothing was contacted
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import ConfigError, load_merged
from .github import Client, GitHubError
from .plan import Action, Plan, plan_labels

HEARTBEAT = Path(".heartbeat")
DRIFT_REPORT = Path(".drift-report.json")


def execute(client: Client, plan: Plan) -> int:
    """Apply the plan's mutations. Returns the number of changes made."""
    changed = 0
    for step in plan.steps:
        if step.action is Action.CREATE:
            client.create_label(step.name, step.color, step.description or "")
            print(f"  created  {step.name}")
            changed += 1
        elif step.action is Action.UPDATE:
            client.update_label(step.name, color=step.color, description=step.description)
            print(f"  updated  {step.name}  ({step.reason})")
            changed += 1
        elif step.action is Action.RENAME:
            client.update_label(
                step.from_name,
                new_name=step.name,
                color=step.color,
                description=step.description,
            )
            print(f"  renamed  {step.from_name} -> {step.name}")
            changed += 1
    return changed


def write_reports(results: list[tuple[str, Plan]]) -> None:
    """Persist the drift report (one entry per target repo) and a heartbeat.

    The heartbeat is how a *silently dead* reconciler becomes visible: a stale
    timestamp is itself drift. Without it, a failed nightly run is invisible
    unless somebody thinks to open the Actions tab.
    """
    now = datetime.now(timezone.utc).isoformat()
    DRIFT_REPORT.write_text(
        json.dumps(
            {
                "checked_at": now,
                "clean": all(plan.is_clean for _, plan in results),
                "repos": [
                    {
                        "repo": repo,
                        "clean": plan.is_clean,
                        "mutations_needed": [s.render() for s in plan.mutations],
                        "extras_not_deleted": [
                            {"name": s.name, "reason": s.reason}
                            for s in plan.of(Action.REPORT_EXTRA)
                        ],
                    }
                    for repo, plan in results
                ],
            },
            indent=2,
        )
    )
    HEARTBEAT.write_text(now + "\n")


def reconcile_repo(config, repo: str, apply: bool) -> tuple[Plan, int]:
    """Reconcile one repo's labels against `config`.

    Returns (final_plan, status) where status is 0 if the repo matches config
    (after applying, when --apply) and 1 on drift or failure. The returned plan
    is the one to record in the drift report — after --apply it is the post-run
    verification plan, so a clean report proves the repo actually converged.
    """
    try:
        client = Client.from_env(repo)
        live = client.list_labels()
    except GitHubError as exc:
        print(f"  github error: {exc}", file=sys.stderr)
        return Plan(steps=()), 1

    print(f"live   : {len(live)} labels on {repo}\n")

    plan = plan_labels(config, live)
    print(plan.render())

    if not apply:
        if plan.is_clean:
            print(f"\n{repo} matches config.")
            return plan, 0
        print(f"\n{len(plan.mutations)} change(s) needed on {repo}. Re-run with --apply.")
        return plan, 1

    if plan.is_clean:
        print(f"\n{repo}: nothing to do.")
        return plan, 0

    print()
    try:
        changed = execute(client, plan)
    except GitHubError as exc:
        print(f"\n{repo}: run failed after partial application: {exc}", file=sys.stderr)
        print("re-run to resume; every step is idempotent.", file=sys.stderr)
        return plan, 1

    # Verify by re-planning against fresh state. A second run must be clean;
    # if it is not, the executor and the planner disagree.
    verify = plan_labels(config, client.list_labels())
    if not verify.is_clean:
        print(f"\napplied {changed} change(s) but {repo} still drifts:", file=sys.stderr)
        print(verify.render(), file=sys.stderr)
        return verify, 1

    print(f"\napplied {changed} change(s); {repo} now matches config.")
    return verify, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pm.reconcile", description=__doc__)
    parser.add_argument(
        "--software",
        required=True,
        metavar="NAME",
        help="load labels from base.yml + config/software/NAME.yml",
    )
    parser.add_argument(
        "--repo",
        metavar="OWNER/NAME",
        default=None,
        help="reconcile only this repo (default: every source_repo in the overlay)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="print the plan, change nothing (default)",
    )
    mode.add_argument("--apply", action="store_true", help="execute the plan")
    args = parser.parse_args(argv)

    # Validate before contacting GitHub, so a bad config can never leave a
    # half-mutated tracker behind.
    try:
        merged = load_merged(args.software)
    except ConfigError as exc:
        print(f"config error:\n{exc}", file=sys.stderr)
        return 2

    config = merged.labels
    targets = [args.repo] if args.repo else list(merged.meta.source_repos)
    if not targets:
        print(f"error: {args.software} declares no source_repos", file=sys.stderr)
        return 2

    print(f"config : {len(config.labels)} labels, {len(config.protected)} protected")
    print(f"targets: {', '.join(targets)}\n")

    results: list[tuple[str, Plan]] = []
    status = 0
    for repo in targets:
        print(f"── {repo} ──────────────────────────────────────────────")
        plan, repo_status = reconcile_repo(config, repo, args.apply)
        results.append((repo, plan))
        status = status or repo_status
        print()

    write_reports(results)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
