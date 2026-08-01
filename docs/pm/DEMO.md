# DEMO — showing the board to the team

You want to open a real board in a screen-share and walk the team through it. This
is the runbook for that. It stands the board up on the **staging** repo you own
(`nishikantmandal007/Osdag-Project-Management`, board **#3**), makes it **public**
so everyone can watch, populates it with real issues, and then hands off to
[SOP-10](SOP-10-osdag-admin-setup.md) for the actual move to `osdag-admin`.

You run this yourself — the one step nobody else can do for you is minting the
**PAT** (it's tied to your account).

---

## First: why you can't see a board yet

Two reasons, both expected:

1. **A user-account Projects V2 board is private by default.** Until you flip
   **Visibility → Public** (step 5), only you can see it. That's why "there's no
   board" — there is one, it's just private to you.
2. **The board on GitHub is stale until the workflows run with a fresh token.**
   All the recent config (Deploy stage field, Merged status, the eight views, the
   renamed title) lives in `config/` in this repo. It is not on the live board
   until `pm-bootstrap-board.yml` runs — and that needs a PAT, because
   `GITHUB_TOKEN` cannot write Projects V2. The earlier PAT is burned; mint a new
   one (step 1).

The board is **hosted on GitHub, not on your laptop**. There is nothing to run
locally for the demo — the "demo" is a live GitHub board you screen-share, with
the [PM Handbook PDF](handbook/osdagbridge-pm-handbook.pdf) as the narration.

---

## The runbook

### 1. Mint a fresh PAT and store it

Follow [SOP-05 § the token](SOP-05-reconciler.md). Fine-grained PAT, 90-day
expiry, with:

- **Account permissions → Projects: Read and write** (the *account* tab — that
  grant is what lets it write a board).
- **Repository permissions → Issues: Read and write** on the source repo in the
  overlay (`nishikantmandal007/OsdagBridge` on staging) — read to pull issues onto
  the board, write so labels-as-code can put `type:/sev:/area:` on them.

Store it as the `GH_PM_TOKEN` secret on this repo:

```
gh secret set GH_PM_TOKEN --repo nishikantmandal007/Osdag-Project-Management
```

> **Never paste the token into a file, a commit, or chat.** It goes into the
> Actions secret and nowhere else.

### 2. Rename board #3 to the new title (one time)

Board #3 was created as "OsdagBridge Delivery"; the overlay title is now
"OsdagBridge", and `find_project` matches on title — so rename in place first, or
a plain bootstrap would create a *second* board:

```
python -m project_management.bootstrap_board \
    --owner nishikantmandal007 --software osdagbridge \
    --rename-from "OsdagBridge Delivery" --apply
```

Idempotent — if the title is already "OsdagBridge" this is a no-op.

### 3. Build the board and start sprint 1 today

```
python -m project_management.bootstrap_board \
    --owner nishikantmandal007 --software osdagbridge \
    --sprint-start today --apply
```

This creates/updates every field (including **Deploy stage** and the **Merged**
status), links the source repo, and builds all eight views. `--sprint-start today`
makes sprint 1 begin on demo day instead of the date frozen in `config/base.yml`
(sprint *length* is unchanged — see [SOP-03](SOP-03-sprint-cadence.md)). Running
it twice changes nothing.

### 4. File the epics and pull the issues in

```
python -m project_management.epics \
    --software osdagbridge --repo nishikantmandal007/OsdagBridge --apply
python -m project_management.bootstrap_board \
    --owner nishikantmandal007 --software osdagbridge --populate --apply
```

`--populate` adds every open issue from the source repo to the board. Now the
board has real content to walk through.

> You can run steps 2–4 from the **Actions** tab instead of a terminal:
> **pm-bootstrap-board**, **pm-epics** workflows → *Run workflow* (they read
> `GH_PM_TOKEN`). Either way is fine; the CLI is easier to narrate.

### 5. Make it public and do the five manual clicks

- **Public:** Board → **Settings** → *Danger zone* → **Visibility: Public**. Now
  the whole team (and the world) can *watch*, read-only. Nobody without board
  **Write** can move a card — see the access-control table in
  [SOP-10](SOP-10-osdag-admin-setup.md#access-control--who-can-do-what).
- **The five workflow clicks:** [BOARD-SETUP](BOARD-SETUP.md) — Auto-add (one per
  source repo), closed→Done, merged→Done, auto-archive, added→Triage. The API
  can't set these; do them once.
- **Two group-by toggles:** the **Release pipeline** view → group by **Deploy
  stage**, and **Workload** → group by **Assignees**. GitHub has no API for a
  view's grouping — one click each ([SOP-08](SOP-08-board-views.md)).

### 6. Verify it's live

Re-run the build — because it's idempotent, a second run against a board that
already matches config **reports no changes**. That "0 mutations" is the proof the
live board matches `config/`:

```
python -m project_management.bootstrap_board \
    --owner nishikantmandal007 --software osdagbridge --apply
```

Then open <https://github.com/users/nishikantmandal007/projects/3> and eyeball it:
title **OsdagBridge**, a **Deploy stage** field, a **Merged** status option, eight
views, and real issues on the board. (`--check` tests the token's permissions if
you suspect a scope problem; `--introspect` dumps the GraphQL field-type shapes
for debugging — neither is the board-state check, the re-run above is.)

---

## Walking the team through it

Screen-share the board with the [handbook PDF](handbook/osdagbridge-pm-handbook.pdf)
open. A ten-minute path:

1. **The problem** (handbook Part I) — 93 ad-hoc issues, 61% unassigned, no way to
   see what's in flight. Show the **Current Sprint** and **Triage Queue** views as
   the answer.
2. **The hierarchy** (Part II) — open one epic, show its sub-issues; explain
   `type:/sev:/area:` on a real issue.
3. **A day in the life** (Part IV) — take one issue from Triage → Ready → In
   Progress → Merged → Done, live, on the board.
4. **The two questions everyone asks** (Part V) — "can outsiders tamper?" (no —
   public is read-only) and "how do interns get on it without repo access?"
   (project access is separate from repo access; three options). Both are in
   [SOP-10](SOP-10-osdag-admin-setup.md).
5. **Where it's going** — the **Release pipeline** view and the conda channels
   ([SOP-11](SOP-11-release-pipeline.md)), and that this same engine runs any
   FOSSEE project from one overlay file.

---

## Then: move to osdag-admin

The staging demo proves the mechanics on a repo you control. Promotion to
`osdag-admin` is the **same commands with a different `--owner`/`source_repos`**,
plus a governance decision that is not yours alone to make:

- The runbook is [SOP-10](SOP-10-osdag-admin-setup.md) (point `source_repos` at
  `osdag-admin/OsdagBridge`, mint a PAT with Issues:write **there**, replay
  steps 2–6).
- The decision — who owns the canonical tracker, what happens to the staging repo
  — is [PROMOTION.md](PROMOTION.md) (T15). **Do not promote before it names a
  contact and a yes.** Everything technical is ready; the agreement is the gate.
