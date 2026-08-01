"""Create or reconcile a project's Projects V2 board from base.yml + its overlay.

    python -m project_management.bootstrap_board --owner LOGIN --software NAME [--apply]

Dry-run by default. Idempotent: fields and views already present are left
alone, so re-running is a no-op and standing up a second project's board is the
same command with a different --software.

The board is linked to the overlay's ``source_repos`` and pulls their issues in
place (``--populate``) — there is no mirror. Never deletes: a field holds every
value set on every item; dropping it discards all of them with no way back.
Extras are reported for a human to remove.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from .config import ConfigError, load_merged
from .project import (
    GraphQL,
    ProjectError,
    add_item,
    create_field,
    create_project,
    create_view,
    find_project,
    link_repository,
    owner_id,
    project_fields,
    project_views,
    rename_project,
    repository_id,
    update_view,
)

# Created by GitHub on every new project. Ours are additive; these are not
# reported as extras and are never touched.
BUILTIN_FIELDS = {
    "Title", "Assignees", "Status", "Labels", "Linked pull requests",
    "Milestone", "Repository", "Reviewers", "Parent issue",
    "Sub-issues progress", "Issue Type",
    # Read-only timestamp fields GitHub adds to every project.
    "Closed", "Created", "Updated",
}


def _merged(software: str | None):
    """Load base.yml + the overlay for ``software``.

    ``--software`` is the only config path now (the monolithic ``project.yml``
    was retired with the mirror). ConfigError is re-raised as ProjectError so
    callers need only one ``except``.
    """
    if not software:
        raise ProjectError("--software NAME is required (config is base.yml + config/software/NAME.yml)")
    try:
        return load_merged(software)
    except ConfigError as exc:
        raise ProjectError(str(exc)) from exc


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


def rename_board(owner: str, old_title: str, apply: bool, software: str | None = None) -> int:
    """One-time in-place rename of a board from OLD_TITLE to the config title.

    ``find_project`` matches on title, so renaming a board is a chicken-and-egg
    step: change the overlay ``display_name`` and a plain bootstrap run stops
    finding the old board and CREATEs a second one. This locates the board by
    its *current* (old) title and moves it to the *new* title the config now
    declares. Idempotent: if the old title is already gone but the new one
    exists, it reports "already renamed" and does nothing.
    """
    try:
        gql = GraphQL.from_env()
        config = _merged(software).board
    except ProjectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    new_title = config["project"]["title"]
    if old_title == new_title:
        print(f"error: --rename-from {old_title!r} equals the config title; nothing to do", file=sys.stderr)
        return 2

    try:
        _, is_org = owner_id(gql, owner)
        old = find_project(gql, owner, old_title, is_org)
        new = find_project(gql, owner, new_title, is_org)
    except ProjectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if old is None:
        if new is not None:
            print(f"already renamed: #{new['number']} is titled {new_title!r} (no board named {old_title!r})")
            return 0
        print(f"error: no board titled {old_title!r} or {new_title!r} owned by {owner}", file=sys.stderr)
        return 1

    if new is not None and new["id"] != old["id"]:
        print(
            f"error: both {old_title!r} (#{old['number']}) and {new_title!r} (#{new['number']}) exist. "
            "Renaming would collide — resolve by hand.",
            file=sys.stderr,
        )
        return 1

    print(f"board  : #{old['number']} {old_title!r} -> {new_title!r}")
    print(f"mode   : {'APPLY' if apply else 'dry-run'}\n")
    if not apply:
        print("dry run; nothing changed. Re-run with --apply")
        return 1

    try:
        renamed = rename_project(gql, old["id"], new_title)
    except ProjectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"renamed: #{renamed['number']} is now titled {renamed['title']!r}")
    return 0


def populate_board(owner: str, apply: bool, software: str | None = None) -> int:
    """Add every open issue in the overlay's source repos to the board, in place.

    Direct-from-repo: the board tracks the SOURCE repos' own issues — there is no
    mirror. The built-in 'Auto-add' workflow only catches issues opened after it
    is enabled, so this one-time backfill sweeps everything already open across
    every ``source_repo``. Idempotent — ``addProjectV2ItemById`` returns the
    existing item for an issue already on the board.

    Deliberately does NOT set Status/Sprint. New items land with no Status (the
    'No Status' column) and no Sprint, which is correct: an un-planned backlog is
    not sprint-planned. That is also why the 'Current Sprint' view is empty —
    nothing is in a sprint yet, by design.
    """
    from .github import Client, GitHubError

    try:
        gql = GraphQL.from_env()
        merged = _merged(software)
    except ProjectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    title = merged.board["project"]["title"]
    source_repos = merged.meta.source_repos
    try:
        _, is_org = owner_id(gql, owner)
        project = find_project(gql, owner, title, is_org)
        if not project:
            print(f"error: no project titled {title!r} — run --apply first", file=sys.stderr)
            return 1
        pid = project["id"]

        # Gather every open issue across all source repos before touching the
        # board, so a bad repo/token fails before any partial backfill.
        per_repo: list[tuple[str, list[dict]]] = []
        for repo in source_repos:
            issues = Client.from_env(repo).list_issues(state="open")
            per_repo.append((repo, issues))
    except (ProjectError, GitHubError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    total = sum(len(issues) for _, issues in per_repo)
    print(f"project: #{project['number']} {title!r}")
    for repo, issues in per_repo:
        print(f"issues : {len(issues)} open in {repo}")
    print(f"mode   : {'APPLY' if apply else 'dry-run'}\n")

    if not apply:
        print(f"would add {total} issue(s) from {len(source_repos)} repo(s) to the board (idempotent)")
        print("\ndry run; nothing changed. Re-run with --apply")
        return 1

    added = 0
    for repo, issues in per_repo:
        for issue in issues:
            add_item(gql, pid, issue["node_id"])
            added += 1
            if added % 20 == 0:
                print(f"  added {added}/{total}")
    print(f"\ndone: {added} issue(s) on the board (duplicates were no-ops)")
    print("Epic Roadmap and Backlog Grooming now populate; Current Sprint stays")
    print("empty until issues are assigned to a sprint.")
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

    # A type reference nests NON_NULL/LIST wrappers arbitrarily deep. Ask for
    # more levels than any real type uses and unwrap to the base named type.
    type_ref = (
        "kind name ofType{ kind name ofType{ kind name ofType{ kind name"
        " ofType{ kind name ofType{ kind name } } } } }"
    )

    def unwrap(ty):
        wraps = []
        while ty and ty.get("ofType"):
            wraps.append(ty["kind"])
            ty = ty["ofType"]
        return wraps, (ty or {}).get("name") or (ty or {}).get("kind")

    def dump_input(tname: str) -> str | None:
        """Print an input type's fields; return the iteration item type name."""
        d = gql(
            "query($n:String!){ __type(name:$n){ kind inputFields{ name type{"
            + type_ref
            + " } } } }",
            n=tname,
        )
        t = d["__type"]
        if not t:
            print(f"\n{tname}: (no such type)")
            return None
        print(f"\n{tname}:")
        item_type = None
        for f in t["inputFields"]:
            wraps, name = unwrap(f["type"])
            required = f["type"]["kind"] == "NON_NULL"
            print(f"  {'REQ ' if required else '    '}{f['name']}: {'/'.join(wraps) or 'scalar'} {name}")
            if f["name"] == "iterations":
                item_type = name
        return item_type

    # 1. Which custom field types actually exist? Settles MULTI_SELECT.
    data = gql('{ __type(name:"ProjectV2CustomFieldType"){ enumValues{ name } } }')
    values = [v["name"] for v in data["__type"]["enumValues"]]
    print("ProjectV2CustomFieldType:", ", ".join(values))
    print("  MULTI_SELECT supported:", "MULTI_SELECT" in values)

    # 2. Iteration config, then the actual list-item type it points at.
    item = dump_input("ProjectV2IterationFieldConfigurationInput")
    if item:
        dump_input(item)
    return 0


def _apply_sprint_start(config: dict, value: str) -> str:
    """Override the Sprint iteration field's start_date in a board config.

    ``value`` is an ISO date (``YYYY-MM-DD``) or the literal ``today``. This is
    how a demo board's first sprint begins on the day it is stood up rather than
    on the date frozen in ``config/base.yml``. Sprint *length* is unchanged —
    only where the numbering starts moves. Returns the resolved date string.

    Raises ProjectError on a malformed date or a board with no ITERATION field.
    """
    if value == "today":
        resolved = date.today().isoformat()
    else:
        try:
            resolved = date.fromisoformat(value).isoformat()
        except ValueError as exc:
            raise ProjectError(
                f"--sprint-start must be YYYY-MM-DD or 'today', got {value!r}"
            ) from exc

    for field in config["fields"]:
        if field.get("type") == "ITERATION":
            field["start_date"] = resolved
            return resolved
    raise ProjectError("this board has no ITERATION (Sprint) field to start")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="project_management.bootstrap_board", description=__doc__)
    parser.add_argument("--owner", required=True, help="user or org login that owns the board")
    parser.add_argument(
        "--repo",
        metavar="OWNER/NAME",
        default=None,
        help="repo to probe with --check (board links come from the overlay's source_repos)",
    )
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
    parser.add_argument(
        "--populate",
        action="store_true",
        help="backfill: add every open source-repo issue to the board (idempotent)",
    )
    parser.add_argument(
        "--rename-from",
        metavar="OLD_TITLE",
        help="one-time in-place rename: move the board titled OLD_TITLE to the "
             "config title (needed after changing an overlay display_name)",
    )
    parser.add_argument(
        "--software",
        metavar="NAME",
        help="build the board from base.yml + config/software/NAME.yml",
    )
    parser.add_argument(
        "--sprint-start",
        metavar="DATE",
        help="date the first sprint starts (YYYY-MM-DD or 'today'); "
             "default: the value in config. Use 'today' for a demo board.",
    )
    args = parser.parse_args(argv)

    if args.check:
        if not args.repo:
            print("error: --check needs --repo OWNER/NAME to probe", file=sys.stderr)
            return 2
        return check_token(args.owner, args.repo)

    if args.introspect:
        return introspect_schema()

    if args.rename_from:
        return rename_board(args.owner, args.rename_from, args.apply, software=args.software)

    if args.populate:
        return populate_board(args.owner, args.apply, software=args.software)

    try:
        merged = _merged(args.software)
        gql = GraphQL.from_env()
    except ProjectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    config = merged.board
    if args.sprint_start:
        try:
            resolved = _apply_sprint_start(config, args.sprint_start)
        except ProjectError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"sprint : first iteration starts {resolved} (--sprint-start)")
    title = config["project"]["title"]
    source_repos = merged.meta.source_repos
    if not source_repos:
        print(f"error: {args.software} declares no source_repos to link", file=sys.stderr)
        return 2
    # The project is created against one repo, then linked to the rest.
    primary_owner, primary_name = source_repos[0].split("/", 1)

    try:
        oid, is_org = owner_id(gql, args.owner)
        print(f"owner  : {args.owner} ({'organization' if is_org else 'user'})")
        if not is_org:
            print("         note: user account - GitHub Issue Types are unavailable here")
            print("         (org-only), which is why work kind lives in `type:` labels.")

        rid = repository_id(gql, primary_owner, primary_name)
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

        pid = project["id"]

        # ── linked repos ──────────────────────────────────────────────────────
        # Direct-from-repo: every source repo is linked so its issues show up on
        # the board. linkProjectV2ToRepository is idempotent, so this is safe to
        # re-run whether the project was just created or already existed.
        print(f"\nrepos  : {len(source_repos)} source repo(s)")
        for repo in source_repos:
            ro, rn = repo.split("/", 1)
            if args.apply:
                link_repository(gql, pid, repository_id(gql, ro, rn))
                print(f"  linked   {repo}")
            else:
                print(f"  LINK     {repo}")

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
    print("  1. Auto-add items from the repo  (one per source repo, see below)")
    print("  2. Item closed        -> Status: Done")
    print("  3. PR merged          -> Status: Done")
    print("  4. Auto-archive items in Done after 14 days")
    print("  5. Item added         -> Status: Triage")
    print("\nAuto-add is per-repo. Add one for each linked source repo:")
    for repo in source_repos:
        print(f"  - {repo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
