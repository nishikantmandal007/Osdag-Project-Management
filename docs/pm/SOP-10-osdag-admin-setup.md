# SOP-10 — Standing the board up on osdag-admin (with access control)

This is the concrete runbook for promotion. **[PROMOTION.md](PROMOTION.md)** owns
the *decision* (is it agreed, who's the contact); this owns the *clicks and
commands* once that decision is made. Do not start until PROMOTION.md has named
answers.

> **Demo note.** For a first run you don't need the real `osdag-admin` repos —
> point the overlay's `source_repos` at a repo you control and follow the same
> steps. The one demo-specific flag is `--sprint-start today` (step 4), so the
> first sprint begins the day you set it up instead of on the date frozen in
> `config/base.yml`.

---

## 0. Prerequisites

- A fine-grained **PAT** (see [SOP-05](SOP-05-reconciler.md)) with:
  - **Account permissions → Projects: Read and write** (the *account* tab, not the
    repo-level "Projects" — the account grant is what lets it write a board).
  - **Repository permissions → Issues: Read and write** on every repo in the
    overlay's `source_repos` (read to pull issues onto the board, write so
    labels-as-code can put `type:/sev:/area:` on the real issues).
  - 90-day expiry; store it as the `GH_PM_TOKEN` secret on the PM repo.
- The overlay (`config/software/<name>.yml`) with `source_repos` pointed at the
  target repos and `board_number` blank (it gets one when the board is created).

---

## 1. Point the overlay at the real repos

Edit `config/software/<name>.yml`:

```yaml
source_repos:
  - osdag-admin/OsdagBridge      # each real code repo the board should track
```

PR it, merge. Everything below reads `source_repos` from here.

## 2. Dry-run the board

```
python -m pm.bootstrap_board --owner osdag-admin --software <name>
```

Dry-run is the default: it prints what it *would* create (project, links, fields,
views) and changes nothing. Read the plan.

## 3. Reconcile the labels onto the source repos

```
python -m pm.reconcile --software <name> --apply
```

Targets every `source_repo`. This needs the PAT's Issues:write on them. Dry-run
first (drop `--apply`) if you want to see the plan.

## 4. Create the board — first sprint starts today

```
python -m pm.bootstrap_board --owner osdag-admin --software <name> \
    --sprint-start today --apply
```

`--sprint-start today` sets the Sprint iteration's first cycle to the setup date;
without it the first sprint uses the date in `config/base.yml`. Sprint *length* is
unchanged (14 days by default — see [SOP-03](SOP-03-sprint-cadence.md) and
[SOP-09 Tutorial 3](SOP-09-customizing.md) to change it). The command creates the
board, links every source repo, and builds all fields and views. It is
idempotent — re-running is a no-op.

After it runs, copy the board number it prints back into the overlay's
`board_number` and commit.

## 5. File the epics and backfill the issues

```
python -m pm.epics --software <name> --repo osdag-admin/OsdagBridge --apply
python -m pm.bootstrap_board --owner osdag-admin --software <name> --populate --apply
```

`--populate` adds every open source-repo issue to the board (idempotent). New
issues opened *after* this are caught by the Auto-add workflow in step 6.

## 6. The manual board workflows

Do the clicks in **[BOARD-SETUP](BOARD-SETUP.md)** — GitHub exposes no API for
these. The one that's per-repo: **one Auto-add per `source_repo`**.

---

## Access control — who can do what

This is the model the team asked for: **everyone sees it, only leads drive it,
nobody can tamper.** It works because GitHub keeps three permissions separate.

### The three surfaces

| Surface | Who can, by default | How to restrict/grant |
|---|---|---|
| **View the board** | Anyone, if the project is **Public** (read-only) | Board → Settings → *Danger zone* → Visibility |
| **Edit the board** (move cards, set Status/Sprint/fields) | Only project collaborators with **Write** or **Admin** | Board → Settings → **Manage access** |
| **Open an issue** | **Any** GitHub user, on a public repo | Repo Settings (issues can be disabled, rarely wanted) |
| **Delete an issue** | Only repo **Admins** | Repo → Settings → Manage access (roles) |

The key fact: **project access is separate from repository access**
(GitHub: *"This only affects collaborators for your project, not for
repositories"*). So you can give a team lead full control of the sprint board
**without** making them a repo collaborator, and a contributor can file issues
**without** any board access.

### Set it up

1. **Make the board public (read-only for the world).**
   Board → **Settings** → *Danger zone* → **Visibility: Public**. Now anyone can
   *watch* progress; a passer-by **cannot** move a card or change a field —
   editing needs Write/Admin, and changing visibility itself is admin-only. Set it
   **Private** instead if you don't want the world watching.

2. **Give team leads board Write.**
   Board → **Settings** → **Manage access** → **Invite collaborators** → add each
   lead → role **Write** ("view and edit the project"). They can now move cards and
   set Status/Sprint/Priority/Owner **with zero repo write access**. Use **Admin**
   only for whoever also manages the project's settings and workflows.

3. **Everyone else: nothing to do.**
   Because the source repos are public, anyone can already **open issues**. They'll
   land on the board via Auto-add. Contributors do **not** need board access to
   file work; they only need it to *edit the board*, which is exactly what you're
   withholding.

4. **Deletion stays locked.**
   Only repo **Admins** can delete an issue — repo *Write* can close/reopen/edit
   but not delete. So "anyone can add, nobody can delete" is the default; just keep
   the Admin role to the few people who own the repo. The nightly reconciler is the
   backstop: any drift (even a legit collaborator's mistaken edit) surfaces in the
   "Board drift detected" issue.

### Assigning work to people without repo access

The board's **Workload** view (below) groups by GitHub's native **Assignees**, but
GitHub only lets you assign someone who is a repo collaborator / has commented / is
an org member. Three ways round it, pick one:

- **(A) Custom "Owner" field** — add a single-select **Owner** field of names; any
  board-Write lead sets it, no repo access needed. Simplest today; group the
  Workload view by **Owner** instead of Assignees.
- **(B) "Comment once" → Assignees** — each person comments on one issue, then is
  assignable via the built-in Assignees field.
- **(C) Convert osdag-admin to an organization** — orgs add **teams + base roles**:
  one `interns` team with **Read** on the repos (→ assignable) and **Write** on the
  project. This scales to 25 far better than inviting individuals (a *user*-owned
  project can only invite people one by one). This is the recommended end-state
  once the team is large.

`osdag-admin` is a **User** account today, so (A) or (B) work now; (C) needs the
org conversion.

---

## Workload — who's carrying the most this sprint

The board ships a **Workload** view (current sprint, open items). Turn on grouping
once, by hand (GitHub has no API for a view's group-by):

- **Workload** tab → **⋯** → **Group by** → **Assignees** (or **Owner**, if you
  chose option A above).

Each person becomes a column; the tallest column is the most-loaded person. For a
trend chart, the board's **Insights** tab plots item counts by assignee over time.
Use this in the sprint review to rebalance — see
[SOP-03](SOP-03-sprint-cadence.md).

---

## Sprint length and other changes

Everything about the board is adjustable after setup — sprint length (7 / 14 / 15
days), fields, labels, epics, even adding a second project. The full "manual UI vs
YAML" guide with worked examples is **[SOP-09](SOP-09-customizing.md)**.
