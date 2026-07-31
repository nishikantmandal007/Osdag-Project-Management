"""Make a GitHub repo match `config/`.

    python -m pm.reconcile --repo owner/name --dry-run
    python -m pm.reconcile --repo owner/name --apply

Defaults to ``--dry-run``: you have to ask for mutations explicitly. Exit codes
are chosen so CI can use this directly:

    0  repo matches config (extras may still be reported)
    1  drift found in --dry-run, or a run failed
    2  config is invalid — nothing was contacted
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import ConfigError, load_labels
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


def write_reports(plan: Plan, repo: str) -> None:
    """Persist the drift report and a heartbeat.

    The heartbeat is how a *silently dead* reconciler becomes visible: a stale
    timestamp is itself drift. Without it, a failed nightly run is invisible
    unless somebody thinks to open the Actions tab.
    """
    now = datetime.now(timezone.utc).isoformat()
    extras = [{"name": s.name, "reason": s.reason} for s in plan.of(Action.REPORT_EXTRA)]
    DRIFT_REPORT.write_text(
        json.dumps(
            {
                "repo": repo,
                "checked_at": now,
                "clean": plan.is_clean,
                "mutations_needed": [s.render() for s in plan.mutations],
                "extras_not_deleted": extras,
            },
            indent=2,
        )
    )
    HEARTBEAT.write_text(now + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pm.reconcile", description=__doc__)
    parser.add_argument("--repo", required=True, metavar="OWNER/NAME")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="print the plan, change nothing (default)",
    )
    mode.add_argument("--apply", action="store_true", help="execute the plan")
    parser.add_argument(
        "--config", type=Path, default=None, help="path to labels.yml (default: config/labels.yml)"
    )
    args = parser.parse_args(argv)

    # Validate before contacting GitHub, so a bad config can never leave a
    # half-mutated tracker behind.
    try:
        config = load_labels(args.config)
    except ConfigError as exc:
        print(f"config error:\n{exc}", file=sys.stderr)
        return 2

    print(f"config : {len(config.labels)} labels, {len(config.protected)} protected")

    try:
        client = Client.from_env(args.repo)
        live = client.list_labels()
    except GitHubError as exc:
        print(f"github error: {exc}", file=sys.stderr)
        return 1

    print(f"live   : {len(live)} labels on {args.repo}\n")

    plan = plan_labels(config, live)
    print(plan.render())
    write_reports(plan, args.repo)

    if not args.apply:
        if plan.is_clean:
            print("\nrepo matches config.")
            return 0
        print(f"\n{len(plan.mutations)} change(s) needed. Re-run with --apply.")
        return 1

    if plan.is_clean:
        print("\nnothing to do.")
        return 0

    print()
    try:
        changed = execute(client, plan)
    except GitHubError as exc:
        print(f"\nrun failed after partial application: {exc}", file=sys.stderr)
        print("re-run to resume; every step is idempotent.", file=sys.stderr)
        return 1

    # Verify by re-planning against fresh state. A second run must be clean;
    # if it is not, the executor and the planner disagree.
    verify = plan_labels(config, client.list_labels())
    write_reports(verify, args.repo)
    if not verify.is_clean:
        print(f"\napplied {changed} change(s) but repo still drifts:", file=sys.stderr)
        print(verify.render(), file=sys.stderr)
        return 1

    print(f"\napplied {changed} change(s); repo now matches config.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
