"""Create the epic issues (L2) from `config/epics.yml`.

    python -m pm.epics --repo OWNER/NAME [--apply]

Dry-run by default. Idempotent: every epic issue carries a hidden marker in its
body (``<!-- pm-epic:KEY -->``), so a re-run finds its own work and creates
nothing twice. E1's six sub-epics are created and linked as native sub-issues.

Never closes or deletes. An epic the config no longer mentions is *reported*,
never touched — closing someone's tracking issue out from under them is exactly
the kind of irreversible act the whole system is built to avoid.
"""

from __future__ import annotations

import argparse
import re
import sys

from .config import ConfigError, EpicConfig, load_epics, load_labels
from .github import Client, GitHubError

# Hidden, stable, and matched verbatim on re-run. KEY is the epic code for a
# top-level epic, or "CODE / SLUG" for a sub-epic.
MARKER_RE = re.compile(r"<!--\s*pm-epic:(.+?)\s*-->")


def _marker(key: str) -> str:
    return f"<!-- pm-epic:{key} -->"


def _epic_body(outcome: str, release: str, code: str, key: str) -> str:
    return (
        f"{outcome}\n\n"
        f"**Release:** {release}\n"
        f"**Board epic:** {code}\n\n"
        f"{_marker(key)}\n"
    )


def _sub_body(parent_code: str, key: str) -> str:
    return (
        f"Sub-epic of **{parent_code}**.\n\n"
        f"{_marker(key)}\n"
    )


def _index_existing(client: Client) -> dict[str, dict]:
    """Map marker KEY -> issue, for every issue this system has already filed."""
    index: dict[str, dict] = {}
    for issue in client.list_issues():
        match = MARKER_RE.search(issue.get("body") or "")
        if match:
            index[match.group(1).strip()] = issue
    return index


def reconcile(repo: str, apply: bool) -> int:
    try:
        labels = load_labels()
        cfg: EpicConfig = load_epics(known_labels=set(labels.by_name()) | {"type:epic"})
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        client = Client.from_env(repo)
        existing = _index_existing(client)
    except GitHubError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    made: dict[str, dict] = dict(existing)  # key -> issue, updated as we create
    n_created = 0
    n_linked = 0

    print(f"repo   : {repo}")
    print(f"mode   : {'APPLY' if apply else 'dry-run'}\n")

    # ── epics ──────────────────────────────────────────────────────────────────
    print("epics:")
    for epic in cfg.epics:
        key = epic.code
        title = f"[Epic] {epic.code}: {epic.title}"
        if key in made:
            print(f"  ok       #{made[key]['number']} {epic.code}")
            continue
        if not apply:
            print(f"  CREATE   {title}")
            continue
        issue = client.create_issue(
            title,
            _epic_body(epic.outcome, epic.release, epic.code, key),
            labels=["type:epic", *epic.areas],
        )
        made[key] = issue
        n_created += 1
        print(f"  created  #{issue['number']} {epic.code}")

    # ── sub-epics + linking ────────────────────────────────────────────────────
    sub_parents = [e for e in cfg.epics if e.sub_epics]
    if sub_parents:
        print("\nsub-epics:")
    for epic in sub_parents:
        parent = made.get(epic.code)
        for sub in epic.sub_epics:
            key = f"{epic.code} / {sub.slug}"
            title = f"[Epic] {epic.code} · {sub.title}"
            if key in made:
                print(f"  ok       #{made[key]['number']} {sub.slug}")
            elif not apply:
                print(f"  CREATE   {title}")
            else:
                issue = client.create_issue(
                    title,
                    _sub_body(epic.code, key),
                    labels=["type:epic", *sub.areas],
                )
                made[key] = issue
                n_created += 1
                print(f"  created  #{issue['number']} {sub.slug}")

            # link child under parent
            child = made.get(key)
            if not apply:
                if parent is None or child is None:
                    print(f"           would link {sub.slug} -> (parent created this run)")
                else:
                    print(f"           would link #{child['number']} -> #{parent['number']}")
                continue
            if parent is None or child is None:
                print(f"           SKIP link {sub.slug}: parent or child missing")
                continue
            newly = client.add_sub_issue(parent["number"], child["id"])
            n_linked += newly
            print(f"           {'linked' if newly else 'already linked'} #{child['number']} -> #{parent['number']}")

    # ── extras (report-only) ───────────────────────────────────────────────────
    known_keys = {e.code for e in cfg.epics} | {
        f"{e.code} / {s.slug}" for e in cfg.epics for s in e.sub_epics
    }
    extras = [k for k in existing if k not in known_keys]
    if extras:
        print("\nextras (marked as epics but absent from config; NOT closed):")
        for key in sorted(extras):
            print(f"  extra    #{existing[key]['number']} {key!r}")

    if not apply:
        print("\ndry run; nothing changed. Re-run with --apply")
        return 1

    print(f"\ndone: {n_created} issue(s) created, {n_linked} sub-issue link(s) added")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pm.epics", description=__doc__)
    parser.add_argument("--repo", required=True, metavar="OWNER/NAME")
    parser.add_argument("--apply", action="store_true", help="execute (default: dry-run)")
    args = parser.parse_args(argv)
    return reconcile(args.repo, args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
