# SOP-08 — Board fields and views reference

Source of truth: the board schema in `config/base.yml`, plus the `Epic` and
`Area` options derived from the project's `config/software/NAME.yml`. This is the
human-readable index. The board is **project #3**,
<https://github.com/users/nishikantmandal007/projects/3>.

## Fields

| Field | Type | Values / notes |
|---|---|---|
| **Status** | single-select | Backlog → Triage → Ready → In Progress → In Review → **Live in Dev** → QA/Verify → Ready for Test → Ready for Prod → In Production → Blocked → On-Hold → Done |
| **Sprint** | iteration (2 wk) | Generated from `start_date: 2026-08-03`, `duration_days: 14` (change these to move/resize sprints — [SOP-03](SOP-03-sprint-cadence.md)) |
| **Type** | single-select | Epic · Feature · Story · Bug · Task · Chore · Spike · Docs · Test — board-visible echo of the `type:` labels so the board can **group** by kind |
| **Priority** | single-select | P0-now · P1-sprint · P2-next · P3-backlog |
| **Severity** | single-select | S1-critical · S2-major · S3-minor · S4-cosmetic |
| **Size** | single-select | XS (≤2h) · S (≤1d) · M (≤3d) · L (≤1wk) · XL (split it) |
| **Points** | number | 1, 2, 3, 5, 8 by convention |
| **Epic** | single-select | E1…E10 (derived from the overlay's `epics:` codes verbatim) |
| **Area** | **multi-select** | Subsystems; multi because issues span two |
| **Team** | single-select | Owning team (derived from the overlay's `teams:` block); each team's `lead` + `members` are the reporting line GitHub can't model |
| **Target release** | single-select | v1.0-GA · v1.1 · v2.0 · future |
| **Start date** | date | Required for the roadmap to render |
| **Target date** | date | Required for the roadmap to render |

**Status — one axis (Maya-style).** There is **one** column. The dev flow and the
release lifecycle are the same axis: a card climbs In Review → **Live in Dev** (PR
merged to the default/dev branch, running in Dev) → QA/Verify → Ready for Test →
Ready for Prod → In Production → Done, so its single Status answers both "is it
built?" and "is it shipped?". The lifecycle tail (Live in Dev onward) is what the
conda release pipeline advances (E6 — [SOP-11](SOP-11-release-pipeline.md)).
**Blocked** and **On-Hold** are off-flow parks. There is no separate *Deploy
stage* field — the release stages that used to live on it are folded into Status,
and **Merged** was renamed **Live in Dev**.

> On a live board the reconciler is report-only: it never deletes. The old
> **Deploy stage** field survives as an unmanaged extra field and the old
> **Merged** Status option survives as a preserved extra option — both are
> *reported*, not removed. Delete them by hand in the UI if you want them gone.

Why some fields are GraphQL-only: `gh` 2.45.0's `field-create` accepts only
TEXT/SINGLE_SELECT/DATE/NUMBER — no ITERATION, no MULTI_SELECT — and has no view
subcommand at all. The whole board is built through GraphQL.

## Views

| View | Layout | Filter | Reads as |
|---|---|---|---|
| **Current Sprint** | Table | `sprint:@current -status:Done,On-Hold` | Active work this sprint, Maya-style: one row per card, columns Title/Status/Assignees/Type/Sprint |
| **Workload** | Board | `sprint:@current is:open` | Who's carrying the most this sprint — **group by Assignees** (manual UI toggle); absorbs the old **By Owner** (identical filter) |
| **By Team** | Board | `is:open` | Every open card by owning team — **group by the Team field** (manual UI toggle) |
| **By Type** | Board | `is:open` | Everything by kind — all epics / all bugs / all features at once — **group by the Type field** (manual UI toggle) |
| **Triage Queue** | Table | `label:status:needs-triage sort:created-asc` | Intake backlog, oldest first |
| **Backlog Grooming** | Table | `no:sprint -label:type:epic is:open` | Unplanned, groomable items |
| **Epic Roadmap** | Roadmap | `label:type:epic` | Outcomes over time (needs date fields) |
| **Release v1.0-GA** | Board | `milestone:v1.0-GA` | What's blocking the release |
| **Release pipeline** | Board | `status:"Live in Dev","Ready for Test","Ready for Prod","In Production"` | The release-lifecycle tail of the single axis — **group by Status** (manual UI toggle) |

Views are created without a filter (`CreateProjectV2ViewInput` has no filter
input) then updated with one — verified against the live schema.

**A view's *group-by* is not an API surface.** GitHub exposes no create/update
mutation for the grouping axis of a view, so **Workload** (group by Assignees),
**By Team** (group by Team), **By Type** (group by Type) and **Release pipeline**
(group by Status) are created with the right *filter* by the bootstrapper but need
one manual UI toggle each: open the view → **⋯** → **Group by** → pick the field.
This is the same class of one-time manual click as the five board workflows in
[BOARD-SETUP](BOARD-SETUP.md).

### Reading the Workload view

Grouped by **Assignees**, each person becomes a column and the column's height is
their open load for the current sprint — the tallest column is the most-loaded
person. Use it in the sprint review to rebalance ([SOP-03](SOP-03-sprint-cadence.md)).
The board's **Insights** tab charts the same by assignee over time. If your team
can't use GitHub's native Assignees (interns without repo access), add a custom
single-select **Owner** field and group by that instead — see
[SOP-10](SOP-10-osdag-admin-setup.md) for the assignment options.

## Expected empties

- **Current Sprint** is empty until issues are assigned a sprint. Correct on a
  fresh backlog.
- **Triage Queue** depends on the `status:needs-triage` **label**, a v2 namespace.
  Until that label ships, triage runs off the board **Status: Triage** column
  instead; the view filter will be flipped to `status:Triage` when the label
  lands. (Tracked with the v2 label rollout.)
- **Epic Roadmap** renders only once epics have Start/Target dates set.

## Changing the board

Edit the board schema in `config/base.yml` (or, for `Epic`/`Area` options, the
project's `config/software/NAME.yml`) in a PR, then run `pm-bootstrap-board.yml`. The
reconciler adds new fields/options and reports extras; it never deletes a field,
because a field holds every value ever set on every item and dropping it discards
them all irrecoverably. Remove a field by hand in the UI, deliberately, if you
really mean to.
