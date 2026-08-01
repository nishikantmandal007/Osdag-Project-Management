# SOP-06 — Intake and promotion

## Intake: direct from the repo

A board tracks its source repos' issues **in place**. There are no copies in the
PM repo — the PM repo holds config and engine only. Each project's overlay
(`config/software/NAME.yml`) declares its `source_repos`, and the board pulls
those repos' issues onto itself.

This replaced an earlier **mirror** model (a seeder that copied upstream issues
into the PM repo with a `<!-- src:REPO#N -->` marker and a backlink). The mirror
is retired — `project_management/seed.py`, `config/seed*.{yml,json}`, `config/issue-map.yml` and
`pm-seed.yml` are gone from the promoted path (still in git history). Direct
intake is simpler and truthful: one issue, one home, no renumbering, no drift
between a copy and its original.

### How a board gets its issues

Three mechanisms, in order of when they run:

1. **Link the source repos.** `pm-bootstrap-board.yml` (`--software NAME`) creates
   the board and calls `link_repository` for every repo in the overlay's
   `source_repos`. Linking is idempotent and is what lets those repos' issues be
   added to the board at all.

2. **Backfill the open issues once.** The `--populate` run of
   `pm-bootstrap-board.yml` iterates every `source_repo`, lists its open issues,
   and adds each to the board via `addProjectV2ItemById` (repo-agnostic — it
   takes any repo's issue node id). Idempotent: re-running adds nothing already
   present.

3. **Catch new issues automatically.** GitHub's built-in **Auto-add** workflow,
   pointed at each source repo, adds issues opened *after* setup. This is a
   manual UI click **per source repo** — see
   [BOARD-SETUP](BOARD-SETUP.md#1-auto-add-items-one-per-source-repo). Backfill
   (step 2) and Auto-add (step 3) are complementary: one catches the past, the
   other the future.

### Labels-as-code now targets the source repos

Because issues live in their own repos, `type:/sev:/area:` labels must exist
**there**, on the real issues:

```
python -m project_management.reconcile --software NAME            # every source_repo in the overlay
python -m project_management.reconcile --software NAME --repo O/N  # just one (e.g. the PM repo itself)
```

The label *config* comes from `--software` (base.yml + the overlay); the
*targets* are the overlay's `source_repos`, unless `--repo` overrides to a single
repo. Reconciling a source repo needs the PAT to have **Issues: write** there —
the same governance gate as promotion (below). The nightly
`pm-reconcile.yml` keeps `--repo <this repo>` so the PM repo's own process
labels (used to file the drift/health issues) stay reconciled without needing
write on anyone else's repo.

### Cutover from the old mirror (board #3)

Board #3 was populated under the mirror model, so it holds ~77 **copied** issues
that live in the PM repo. There is **no seamless in-place migration** of those
copies to direct-from-repo — a copy and its source are different issues with
different numbers. To cut a mirror-era board over:

1. Link the real source repos (`--software`, as above) and `--populate` to pull
   their live issues onto the board alongside the old copies.
2. Enable per-repo Auto-add for each source repo.
3. Treat the mirrored copies as historical staging data: leave them as a frozen
   record, or remove them by hand. The reconciler **never** closes or deletes
   them for you — doing that to someone's issue is exactly the irreversible act
   the system avoids.

For a fresh project there is no cutover: its board is direct-from-repo from the
first `--populate`.

### Removing the old mirrored copies (optional, manual)

The mirror-era copies live **in the PM repo** and each carries a
`<!-- src:OWNER/REPO#N -->` marker in its body — that's how to tell a copy from a
real issue. Removal is deliberately manual and **not scripted**: deleting a GitHub
issue is irreversible and needs repo **Admin**, so a human does it with eyes open.

To find them:

```
gh issue list -R nishikantmandal007/osdagbridge-pm --state all --limit 200 \
  --search '"<!-- src:" in:body' --json number,title
```

Then, once you've confirmed the list is only mirror copies:

- **Keep as history (recommended default):** do nothing. They stay as a frozen
  staging record. New work is tracked directly on the source repos.
- **Close them:** `gh issue close <N> -R nishikantmandal007/osdagbridge-pm` per
  number — reversible, keeps the thread.
- **Delete them:** Issue → **⋯** → **Delete issue** in the UI (repo Admin only),
  or `gh issue delete <N> -R … --yes`. Irreversible; only for a demo repo you own.

Do this against the **PM repo**, never a source repo — the source repos hold the
real issues.

---

## Promotion

Promotion means standing this system up against the real tracker
(`osdag-admin/OsdagBridge` and its siblings) once it's validated here. **It is
not one command** — the reasons are structural, not laziness:

1. **The board workflows are manual, once per source repo.**
   ([BOARD-SETUP](BOARD-SETUP.md).) Whoever promotes clicks through them again on
   the target board — including one Auto-add per source repo.
2. **The engine is fully parameterised** — `--software`, `--owner`, `--repo`. The
   overlay's `source_repos` decide what the board tracks. Point an overlay at the
   real repos and the labels, epics, fields and views replay against them. That
   part is one command per piece.
3. **The PAT needs write on the real repos.** Direct intake means labels-as-code
   writes `type:/sev:/area:` onto the source repos' issues, so the PAT needs
   **Issues: read + write** on each. On staging, point `source_repos` at repos
   the user controls; for the real `osdag-admin` repos this is the unowned
   governance decision in **[PROMOTION.md](PROMOTION.md)** (T15) — currently the
   real blocker.

**Do not promote before PROMOTION.md names a contact and a decision.** Everything
technical is ready; the agreement is not.
