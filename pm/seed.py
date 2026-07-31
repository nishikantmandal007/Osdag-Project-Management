"""Mirror the source tracker's open issues into this repo.

    python -m pm.seed --repo OWNER/NAME [--apply] [--limit N]

Dry-run by default. Reads a COMMITTED snapshot (config/seed-source.json), not
the live source repo — reproducible, reviewable, and independent of whether the
token can read another user's repo.

Idempotent. Every mirrored issue ends with `<!-- src:<source_repo>#N -->`; a
re-run indexes the target repo by that marker and recreates nothing. Strictly
one-way: it never edits or closes anything in the source.

Two passes when needed:
  1. create every missing mirror (building the source#->target# map)
  2. rewrite bare `#N` cross-references in mirrored bodies to their new target
     numbers, since seeding renumbers everything. The backlink and marker carry
     the SOURCE number and are assembled around the rewritten body, so they are
     never touched.

Today's snapshot contains zero cross-references, so pass 2 is a verified no-op —
but it is correct if the source ever gains them.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from .config import ConfigError, SeedConfig, load_labels, load_seed
from .github import Client, GitHubError


def marker(source_repo: str, number: int) -> str:
    return f"<!-- src:{source_repo}#{number} -->"


# Captures the source number from a mirror's marker, for idempotency indexing.
def _marker_re(source_repo: str) -> re.Pattern:
    return re.compile(r"<!--\s*src:" + re.escape(source_repo) + r"#(\d+)\s*-->")


# A bare cross-reference: #123 not preceded by a word char or a '/' (so
# "owner/repo#123" backlinks are left alone) and not inside a URL.
_BARE_REF_RE = re.compile(r"(?<![\w/])#(\d+)\b")


def _backlink(cfg: SeedConfig, issue: dict) -> str:
    return (
        f"> Mirrored from [{cfg.source_repo}#{issue['number']}]({issue['html_url']}) — "
        f"originally filed by @{issue['user']} on {issue['created_at'][:10]}."
    )


def rewrite_refs(body: str, src_to_target: dict[int, int]) -> str:
    """Rewrite bare `#N` where N is a known source number, to `#<target>`."""
    def repl(m: re.Match) -> str:
        n = int(m.group(1))
        return f"#{src_to_target[n]}" if n in src_to_target else m.group(0)

    return _BARE_REF_RE.sub(repl, body or "")


def _assemble(cfg: SeedConfig, issue: dict, src_to_target: dict[int, int]) -> str:
    original = rewrite_refs(issue.get("body") or "", src_to_target)
    return (
        f"{_backlink(cfg, issue)}\n\n"
        f"{original}\n\n"
        f"{marker(cfg.source_repo, issue['number'])}"
    )


def _index_existing(client: Client, source_repo: str) -> dict[int, dict]:
    """Map source number -> already-mirrored target issue."""
    pat = _marker_re(source_repo)
    index: dict[int, dict] = {}
    for issue in client.list_issues():
        m = pat.search(issue.get("body") or "")
        if m:
            index[int(m.group(1))] = issue
    return index


def reconcile(repo: str, apply: bool, limit: int | None) -> int:
    try:
        labels = load_labels()
        cfg = load_seed(known_labels=set(labels.by_name()))
        source = json.loads(cfg.snapshot.read_text())
    except (ConfigError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    source.sort(key=lambda i: i["number"])
    if limit is not None:
        source = source[:limit]

    try:
        client = Client.from_env(repo)
        existing = _index_existing(client, cfg.source_repo)
    except GitHubError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"source : {cfg.source_repo} ({len(source)} open issue(s) in snapshot)")
    print(f"target : {repo}")
    print(f"mode   : {'APPLY' if apply else 'dry-run'}")
    print(f"already mirrored: {len(existing)}\n")

    # Full map for ref-rewriting: existing mirrors + everything we create.
    src_to_target: dict[int, int] = {n: iss["number"] for n, iss in existing.items()}
    unmapped_labels: set[str] = set()
    created: list[tuple[int, dict]] = []
    n_new = 0

    # ── pass 1: create missing mirrors ─────────────────────────────────────────
    for issue in source:
        num = issue["number"]
        tgt_labels, unmapped = cfg.map_labels(issue["labels"])
        unmapped_labels.update(unmapped)

        if num in existing:
            print(f"  ok       src#{num} -> #{existing[num]['number']}")
            continue
        title = issue["title"]
        if not apply:
            lbls = ",".join(tgt_labels) or "(none)"
            print(f"  CREATE   src#{num}  {title[:60]!r}  [{lbls}]")
            continue

        body = _assemble(cfg, issue, src_to_target)  # map filled as we go
        made = client.create_issue(title, body, labels=tgt_labels or None)
        existing[num] = made
        src_to_target[num] = made["number"]
        created.append((num, made))
        n_new += 1
        print(f"  created  src#{num} -> #{made['number']}  [{','.join(tgt_labels) or 'none'}]")

    # ── pass 2: rewrite cross-references now the whole map is known ─────────────
    n_rewritten = 0
    if apply:
        for num, made in created:
            src_issue = next(i for i in source if i["number"] == num)
            desired = _assemble(cfg, src_issue, src_to_target)
            if desired != made.get("body"):
                client.update_issue_body(made["number"], desired)
                n_rewritten += 1

    # ── issue-map + label-gap report ───────────────────────────────────────────
    if unmapped_labels:
        print("\nunmapped source labels (mirrored without a tag; add to seed.yml when v2 lands):")
        for lbl in sorted(unmapped_labels):
            print(f"  gap      {lbl!r}")

    if apply:
        _write_issue_map(cfg, existing)
        print(f"\nwrote config/issue-map.yml ({len(existing)} entries)")

    if not apply:
        print("\ndry run; nothing changed. Re-run with --apply")
        return 1

    print(f"\ndone: {n_new} mirrored, {n_rewritten} body rewrite(s)")
    return 0


def _write_issue_map(cfg: SeedConfig, existing: dict[int, dict]) -> None:
    from .config import CONFIG_DIR

    lines = [
        "# Generated by pm.seed — source issue number -> mirrored target number.",
        "# Do not edit by hand; re-running the seeder regenerates it.",
        f"source_repo: {cfg.source_repo}",
        "map:",
    ]
    for num in sorted(existing):
        lines.append(f"  {num}: {existing[num]['number']}")
    (CONFIG_DIR / "issue-map.yml").write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pm.seed", description=__doc__)
    parser.add_argument("--repo", required=True, metavar="OWNER/NAME")
    parser.add_argument("--apply", action="store_true", help="execute (default: dry-run)")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="only process the first N source issues (for a cautious first run)",
    )
    args = parser.parse_args(argv)
    return reconcile(args.repo, args.apply, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
