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
        # Distinguish "wrong repo selected" from "token cannot see ANY private
        # repo". The second means the token was created in 'Public repositories'
        # access mode, which cannot be fixed by adding a repository — the mode
        # itself has to change.
        try:
            private = gql(
                "{ viewer { repositories(first:1, privacy:PRIVATE, affiliations:[OWNER])"
                " { totalCount } } }"
            )["viewer"]["repositories"]["totalCount"]
        except ProjectError:
            private = -1

        if private == 0:
            detail = (
                f"{repo} NOT visible, and this token can see ZERO private repos.\n"
                "        That means its 'Repository access' is set to "
                "'Public repositories'.\n"
                "        Adding a repo will not help — change the mode to "
                "'Only select repositories'\n"
                "        (or 'All repositories'), then pick "
                f"{repo_name}. Metadata: Read-only is the minimum."
            )
        elif private > 0:
            detail = (
                f"{repo} NOT visible, though the token does see {private} other "
                "private repo(s).\n"
                f"        So the mode is right but {repo_name} is not in the "
                "selected list — add it.\n"
                "        If you edited a different token, update the "
                "GH_PM_TOKEN secret too."
            )
        else:
            detail = f"{repo} NOT visible — add it under 'Repository access' (Metadata: Read-only)"
        results.append((False, "repository access", detail))

    # 3. Projects. Account-level on user accounts, NOT the similarly-named
    #    repository-level 'Projects' permission.
    #
    #    Assert on the returned value, not merely on the absence of an
    #    exception: an inline fragment that the token cannot satisfy comes back
    #    as null with no error, which previously read as a false 'ok'.
    projects_note = (
        "Grant ACCOUNT permission 'Projects: Read and write'.\n"
        "        Careful: there are two permissions called 'Projects'. The one\n"
        "        under 'Repository permissions' is for old repo-scoped boards and\n"
        "        does NOT work. You need the one under 'Account permissions',\n"
        "        further down the token page."
    )
    try:
        data = gql("{ viewer { projectsV2(first:1){ totalCount } } }")
        node = (data.get("viewer") or {}).get("projectsV2")
        if node is None:
            results.append(
                (False, "projects access", f"query returned null — token has no Projects access.\n        {projects_note}")
            )
        else:
            results.append((True, "projects access", f"can read projects ({node['totalCount']} existing)"))
    except ProjectError as exc:
        results.append((False, "projects access", f"{exc}\n        {projects_note}"))

    # 3b. Node-probe. `totalCount` can succeed while enumerating `nodes` is
    #     rejected with "Resource not accessible by personal access token" —
    #     that is a field-level denial, not a read/write one. Walk from the
    #     cheapest selection to the full one so the FIRST failure names the
    #     exact field the token cannot read, in a single CI round trip.
    probes = [
        ("nodes{ id }",                 "{ viewer { projectsV2(first:100){ nodes{ id } } } }"),
        ("nodes{ id number }",          "{ viewer { projectsV2(first:100){ nodes{ id number } } } }"),
        ("nodes{ id number title }",    "{ viewer { projectsV2(first:100){ nodes{ id number title } } } }"),
        ("nodes{ id number title url }","{ viewer { projectsV2(first:100){ nodes{ id number title url } } } }"),
    ]
    probe_note = (
        "totalCount works but enumerating project nodes is denied. This is a\n"
        "        field-level denial. Two known causes:\n"
        "          - the token was minted before the account 'Projects' permission\n"
        "            was set to Read and write — regenerate it (a saved token does\n"
        "            NOT pick up a later permission change), OR\n"
        "          - the 'url' field specifically requires the write scope; the\n"
        "            code now avoids it and reads only id/number/title."
    )
    first_fail = None
    for shape, q in probes:
        try:
            gql(q)
        except ProjectError as exc:
            first_fail = (shape, str(exc))
            break
    if first_fail is None:
        results.append((True, "projects node read", "can enumerate project nodes (id/number/title/url)"))
    else:
        shape, msg = first_fail
        results.append(
            (False, "projects node read", f"first denied at `{shape}`: {msg}\n        {probe_note}")
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


def introspect_schema() -> int:
    """Print the live shape of the two things this board bends on.

    ``gh`` documents its own field-create limits, not the API's; and the
    iteration input's required members are not in any doc I trust. Read them
    straight from the running schema so the fix is against reality, not memory.
    """
    try:
        gql = GraphQL.from_env()
    except ProjectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # 1. Which custom field types actually exist? Settles MULTI_SELECT.
    data = gql('{ __type(name:"ProjectV2CustomFieldType"){ enumValues{ name } } }')
    values = [v["name"] for v in data["__type"]["enumValues"]]
    print("ProjectV2CustomFieldType:", ", ".join(values))
    print("  MULTI_SELECT supported:", "MULTI_SELECT" in values)

    # 2. Required members of the iteration config (the null it just rejected).
    for tname in (
        "ProjectV2IterationFieldConfigurationInput",
        "ProjectV2IterationFieldIterationInput",
    ):
        d = gql(
            'query($n:String!){ __type(name:$n){ inputFields{'
            " name type{ kind name ofType{ kind name ofType{ kind name } } } } } }",
            n=tname,
        )
        t = d["__type"]
        if not t:
            print(f"\n{tname}: (no such type)")
            continue
        print(f"\n{tname}:")
        for f in t["inputFields"]:
            ty = f["type"]
            required = ty["kind"] == "NON_NULL"
            # peel NON_NULL / LIST wrappers to the underlying name
            core = ty
            wraps = []
            while core and core.get("ofType"):
                wraps.append(core["kind"])
                core = core["ofType"]
            name = (core or {}).get("name") or (core or {}).get("kind")
            print(f"  {'REQ ' if required else '    '}{f['name']}: {'/'.join(wraps) or ''} {name}")
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
    parser.add_argument(
        "--introspect",
        action="store_true",
        help="dump the exact field-type enum and iteration input shape, then exit",
    )
    args = parser.parse_args(argv)

    if args.check:
        return check_token(args.owner, args.repo)

    if args.introspect:
        return introspect_schema()

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
