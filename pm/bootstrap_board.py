"""Create or reconcile the Projects V2 board from `config/project.yml`.

    python -m pm.bootstrap_board --owner LOGIN --repo OWNER/NAME [--apply]

Dry-run by default. Idempotent: fields and views already present are left
alone, so re-running is a no-op and promotion to another repo is the same
command with a different --owner/--repo.

Never deletes. A field holds every value set on every item; dropping it discards
all of them with no way back. Extras are reported for a human to remove.
"""

from __future__ import annotations

import argparse
import sys

from .project import (
    GraphQL,
    ProjectError,
    create_field,
    create_project,
    create_view,
    find_project,
    link_repository,
    load_project_config,
    owner_id,
    project_fields,
    project_views,
    repository_id,
    update_view,
)

# Created by GitHub on every new project. Ours are additive; these are not
# reported as extras and are never touched.
BUILTIN_FIELDS = {
    "Title", "Assignees", "Status", "Labels", "Linked pull requests",
    "Milestone", "Repository", "Reviewers", "Parent issue",
    "Sub-issues progress", "Issue Type",
}


def check_token(owner: str, repo: str) -> int:
    """Probe each permission separately and report every failure in one pass.

    Fixing a PAT one error at a time costs a round trip through the GitHub UI
    per attempt, so this tests all three things the board needs and prints a
    single verdict.
    """
    try:
        gql = GraphQL.from_env()
    except ProjectError as exc:
        print(f"FAIL  token: {exc}")
        return 2

    repo_owner, repo_name = repo.split("/", 1)
    results: list[tuple[bool, str, str]] = []

    # 1. Is the token valid at all?
    try:
        who = gql("{ viewer { login } }")["viewer"]["login"]
        results.append((True, "authentication", f"as {who}"))
    except ProjectError as exc:
        print(f"FAIL  authentication: {exc}")
        return 1

    # 2. Metadata read on the target repo.
    try:
        gql(
            "query($o:String!,$n:String!){ repository(owner:$o,name:$n){ id } }",
            o=repo_owner,
            n=repo_name,
        )
        results.append((True, "repository access", f"{repo} is visible"))
    except ProjectError:
        results.append(
            (
                False,
                "repository access",
                f"{repo} NOT visible — add it under 'Repository access' "
                "and grant 'Metadata: Read-only'",
            )
        )

    # 3. Projects read. Account-level on user accounts, not per-repo.
    try:
        gql(
            "query($l:String!){ repositoryOwner(login:$l){ ... on ProjectV2Owner "
            "{ projectsV2(first:1){ totalCount } } } }",
            l=owner,
        )
        results.append((True, "projects read", "ok"))
    except ProjectError as exc:
        results.append(
            (
                False,
                "projects read",
                f"{exc} — grant Account permission 'Projects: Read and write'",
            )
        )

    for ok, name, detail in results:
        print(f"{'ok  ' if ok else 'FAIL'}  {name}: {detail}")

    failed = [r for r in results if not r[0]]
    if failed:
        print(f"\n{len(failed)} permission problem(s). Edit the token at")
        print("github.com/settings/personal-access-tokens, then re-run this check.")
        return 1

    print("\nToken has everything the board needs.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pm.bootstrap_board", description=__doc__)
    parser.add_argument("--owner", required=True, help="user or org login that owns the board")
    parser.add_argument("--repo", required=True, metavar="OWNER/NAME", help="repo to link")
    parser.add_argument("--apply", action="store_true", help="execute (default: dry-run)")
    parser.add_argument(
        "--check",
        action="store_true",
        help="test every token permission independently and report all failures at once",
    )
    args = parser.parse_args(argv)

    if args.check:
        return check_token(args.owner, args.repo)

    try:
        config = load_project_config()
        gql = GraphQL.from_env()
    except ProjectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    title = config["project"]["title"]
    repo_owner, repo_name = args.repo.split("/", 1)

    try:
        oid, is_org = owner_id(gql, args.owner)
        print(f"owner  : {args.owner} ({'organization' if is_org else 'user'})")
        if not is_org:
            print("         note: user account - GitHub Issue Types are unavailable here")
            print("         (org-only), which is why work kind lives in `type:` labels.")

        rid = repository_id(gql, repo_owner, repo_name)
        project = find_project(gql, args.owner, title, is_org)

        # ── project ──────────────────────────────────────────────────────────
        if project:
            print(f"project: #{project['number']} {title!r} (exists)")
        elif not args.apply:
            print(f"project: would CREATE {title!r}")
            print("\ndry run; re-run with --apply")
            return 1
        else:
            project = create_project(gql, oid, title, rid)
            print(f"project: CREATED #{project['number']} -> {project['url']}")
            link_repository(gql, project["id"], rid)
            print(f"         linked to {args.repo}")

        pid = project["id"]

        # ── fields ───────────────────────────────────────────────────────────
        existing = project_fields(gql, pid)
        desired = {f["name"]: f for f in config["fields"]}
        creates = [f for name, f in desired.items() if name not in existing]

        print(f"\nfields : {len(existing)} present, {len(creates)} to create")
        for spec in creates:
            if args.apply:
                create_field(gql, pid, spec)
                print(f"  created  {spec['name']} ({spec['type']})")
            else:
                print(f"  CREATE   {spec['name']} ({spec['type']})")

        for name in sorted(existing):
            if name not in desired and name not in BUILTIN_FIELDS:
                print(f"  extra    {name!r} (not in config; not deleted)")

        # ── views ────────────────────────────────────────────────────────────
        live_views = project_views(gql, pid)
        print(f"\nviews  : {len(live_views)} present")
        for spec in config["views"]:
            name = spec["name"]
            if name in live_views:
                print(f"  ok       {name}")
                continue
            if not args.apply:
                print(f"  CREATE   {name} ({spec['layout']}) filter={spec['filter']!r}")
                continue
            # createProjectV2View takes no filter; set it in a second call.
            view = create_view(gql, pid, name, spec["layout"])
            update_view(gql, view["id"], spec["filter"])
            print(f"  created  {name} ({spec['layout']}) + filter")

    except ProjectError as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1

    if not args.apply:
        print("\ndry run; nothing changed. Re-run with --apply")
        return 1

    print(f"\nboard ready: {project.get('url', '(existing)')}")
    print("\nSTILL MANUAL - GitHub exposes no create/update mutation for built-in")
    print("board workflows. Enable these five in the UI (docs/pm/BOARD-SETUP.md):")
    print("  1. Auto-add items from the repo")
    print("  2. Item closed        -> Status: Done")
    print("  3. PR merged          -> Status: Done")
    print("  4. Auto-archive items in Done after 14 days")
    print("  5. Item added         -> Status: Triage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
