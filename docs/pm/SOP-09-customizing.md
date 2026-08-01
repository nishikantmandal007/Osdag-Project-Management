# SOP-09 — Customizing the board (manual UI *and* YAML)

Almost everything here can be done **two ways**, and they coexist:

- **YAML** — edit `config/`, open a PR, run the workflow. Reviewable, replayable,
  survives a rebuild-from-scratch. This is how the board is promoted to another
  repo unchanged.
- **Manual UI** — click it in GitHub. Instant, no PR, but invisible to the
  reconciler and lost if the board is ever rebuilt from config.

The golden rule makes the two safe together: **the reconciler never deletes.**
Anything you add by hand that config doesn't know about is *reported as an extra*,
never removed. Anything in config that's missing is *added*. So you can hand-tweak
freely and formalise it in YAML later, or never — nothing you clicked gets
clobbered except the fields config explicitly owns (see the table at the bottom).

Config lives in two layers:

- `config/base.yml` — shared across every project (the `type:`/`sev:` labels,
  Status/Priority/Size/Points fields, the Sprint schedule, the board views).
- `config/software/<name>.yml` — one file per project (`display_name`,
  `area:` labels, `epics:`, `source_repos:`, `board_number`, `conda_channels`).

`load_merged(name)` stitches them together; the `Epic` and `Area` board options
are *derived* from the overlay, so you never write them twice.

---

## Quick reference — which file, which command

| Change | YAML: edit… | then run | Manual UI alternative |
|---|---|---|---|
| Add/rename a **label** or area | `base.yml` (`type:`/`sev:`) or overlay (`area:`) | `pm-reconcile` | Issues → Labels → New (reported as extra until added to config) |
| Add/change an **epic** | overlay `epics:` | `pm-epics` | Open an issue with `<!-- pm-epic:KEY -->` in the body (reconciler adopts it) |
| Add a **board field / option** | `base.yml` `fields:` | `pm-bootstrap-board` | Board → ＋ → New field |
| Add a **view** | `base.yml` `views:` | `pm-bootstrap-board` | Board → new tab |
| Change **sprint length / start** | `base.yml` Sprint field, or `--sprint-start` | `pm-bootstrap-board` | Board → Sprint field → Edit iterations |
| Add a whole **new project** | new `config/software/<name>.yml` | `pm-bootstrap-board --software <name>` | — (config is the only sane path) |
| Rename a **board** | overlay `display_name` | `pm-bootstrap-board --rename-from` | Board → ⋯ → Settings → rename |

---

## Tutorial 1 — add a new area label

Say a project grows a "installer" subsystem and you want an `area:installer`
label so issues can be tagged and the board's **Area** field offers it.

**YAML way**

1. Open `config/software/osdagbridge.yml`, find `area_labels.labels:` and add a
   code-side area (colour is *derived* — code areas render BLUE, UI areas with an
   `alias:` render PURPLE, so you don't set colour here):
   ```yaml
   - {name: "area:installer", description: "Windows/Linux installer & packaging"}
   ```
2. PR it, merge.
3. Run **Reconcile** (`pm-reconcile.yml`, dispatch, *Apply* checked) to create the
   label on the source repos, and **Bootstrap board** (`pm-bootstrap-board.yml`,
   *Apply*) so the derived **Area** option appears on the board.

**Manual way**

- Repo → Issues → **Labels** → **New label**, name `area:installer`. It exists
  immediately. On the next nightly reconcile it shows as an *extra* ("not in
  config") — that's expected; move it into the overlay when you want it permanent.

They don't conflict: if you created it by hand first, the reconcile step above is
a no-op for that label (already present).

## Tutorial 2 — add an epic

**YAML way** — add an entry under the overlay's `epics.items:` list (each `area`
must already exist in `area_labels`):

```yaml
- code: "E11 telemetry"
  title: "Opt-in usage telemetry"
  release: "v1.1"
  areas: [area:ci-cd]
  outcome: >
    Crash rate and feature usage are visible without touching user data.
```

PR, merge, run **Epics** (`pm-epics.yml`, *Apply*). It files the epic issue with a
hidden `<!-- pm-epic:E11 telemetry -->` marker and — because the marker is how
re-runs stay idempotent — creates it exactly once. The board's **Epic** field
gains `E11 telemetry` automatically (it's derived); run **Bootstrap board** to
apply that field change.

**Manual way** — open an issue titled `[Epic] E11: …` and paste
`<!-- pm-epic:E11 telemetry -->` anywhere in the body. The next `pm-epics` run
*adopts* it (reports "ok", creates nothing). Omit the marker and it's a normal
issue the epic tooling ignores — also fine for a one-off.

Either way the reconciler **never closes** an epic, even one you later remove from
config; it only reports it.

## Tutorial 3 — change the sprint length

The Sprint field is a Projects V2 **iteration**. Its length lives in
`config/base.yml`:

```yaml
- name: Sprint
  type: ITERATION
  duration_days: 14        # <- change to 7 for weekly, 15 for a fortnight-plus
  start_date: "2026-08-03"
```

- **7-day sprints:** set `duration_days: 7`.
- **15-day sprints:** set `duration_days: 15`.

Then run **Bootstrap board**. Note GitHub generates iterations *forward* from
`start_date`; changing the length reshapes future iterations. To also move where
the numbering begins — for a fresh demo, "start today" — pass
`--sprint-start today` (or a specific `YYYY-MM-DD`) to `pm-bootstrap-board`
instead of editing `start_date`. See [SOP-03](SOP-03-sprint-cadence.md).

**Manual way** — Board → **Sprint** field → **Edit iterations** → change the
duration / add iterations. Instant, but the config's `duration_days` still wins
the next time anyone runs Bootstrap board, so change both if you want it to stick.

## Tutorial 4 — add a whole new project

This is the payoff of base+overlay: a second board is one file.

1. Copy `config/software/osdagbridge.yml` to `config/software/<name>.yml`.
2. Edit `display_name`, `source_repos`, `area_labels`, `epics`, `conda_channels`,
   `board_number` (leave `board_number` blank until the board exists).
3. Add `<name>` to `config/rollup.yml`'s Software options so it appears on the
   "All Projects" roll-up.
4. PR, merge.
5. Run **Bootstrap board** with `--software <name>` — it creates the board, links
   every `source_repo`, and builds the fields and views. Use `--sprint-start
   today` for a demo.
6. Run **Epics** and **Reconcile** with the same `--software <name>`.
7. Do the manual clicks in [BOARD-SETUP](BOARD-SETUP.md): one **Auto-add** per
   source repo, plus the four status workflows.

Nothing about the engine changed — same commands, different `--software`.

## Tutorial 5 — the Workload view (who has the most work)

The board ships a **Workload** view (current sprint, open items). GitHub can't set
a view's *group-by* through the API, so switch it on once by hand:

- Open the **Workload** tab → **⋯** → **Group by** → **Assignees**.

Each person becomes a column; the column's height is their load this sprint. For a
chart, the board's **Insights** tab (top-right) plots items by assignee over time —
also UI-only. If your team can't use GitHub's native **Assignees** (see
[BOARD-SETUP](BOARD-SETUP.md) and the handbook's open-source chapter), add a custom
single-select **Owner** field and group by that instead.

---

## What config *owns* (do not hand-edit these)

The reconciler will overwrite these on the next run, because they're declared in
config — change them there, not in the UI:

- Status column set, colours, and order.
- The Sprint iteration schedule (length + start).
- Every single-select / multi-select field's option set.
- Label colours and descriptions on the source repos.

Everything else — assignees, which card is in which status, custom notes, the
five manual board workflows, view group-by toggles — is yours to click and the
reconciler leaves alone.

See also: [SOP-04](SOP-04-epics.md) (epics), [SOP-05](SOP-05-reconciler.md)
(how the never-delete reconciler works), [SOP-08](SOP-08-board-views.md) (the
full field/view reference), [SOP-10](SOP-10-osdag-admin-setup.md) (standing the
board up on osdag-admin with access control).
