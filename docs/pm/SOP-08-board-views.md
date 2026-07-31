# SOP-08 — Board fields and views reference

Source of truth: `config/project.yml`. This is the human-readable index. The
board is **project #3**, <https://github.com/users/nishikantmandal007/projects/3>.

## Fields

| Field | Type | Values / notes |
|---|---|---|
| **Status** | single-select | Backlog → Triage → Ready → In Progress → In Review → QA/Verify → Blocked → Done |
| **Sprint** | iteration (2 wk) | Generated from `start_date: 2026-08-03`, `duration_days: 14` |
| **Priority** | single-select | P0-now · P1-sprint · P2-next · P3-backlog |
| **Severity** | single-select | S1-critical · S2-major · S3-minor · S4-cosmetic |
| **Size** | single-select | XS (≤2h) · S (≤1d) · M (≤3d) · L (≤1wk) · XL (split it) |
| **Points** | number | 1, 2, 3, 5, 8 by convention |
| **Epic** | single-select | E1…E10 (matches `config/epics.yml` codes verbatim) |
| **Area** | **multi-select** | Subsystems; multi because issues span two |
| **Target release** | single-select | v1.0-GA · v1.1 · v2.0 · future |
| **Start date** | date | Required for the roadmap to render |
| **Target date** | date | Required for the roadmap to render |

Why some fields are GraphQL-only: `gh` 2.45.0's `field-create` accepts only
TEXT/SINGLE_SELECT/DATE/NUMBER — no ITERATION, no MULTI_SELECT — and has no view
subcommand at all. The whole board is built through GraphQL.

## Views

| View | Layout | Filter | Reads as |
|---|---|---|---|
| **Current Sprint** | Board | `sprint:@current -status:Done` | Active work this sprint |
| **Triage Queue** | Table | `label:status:needs-triage sort:created-asc` | Intake backlog, oldest first |
| **Backlog Grooming** | Table | `no:sprint -label:type:epic is:open` | Unplanned, groomable items |
| **Epic Roadmap** | Roadmap | `label:type:epic` | Outcomes over time (needs date fields) |
| **Release v1.0-GA** | Board | `milestone:v1.0-GA` | What's blocking the release |
| **By Owner** | Board | `sprint:@current is:open` | Who's carrying what |

Views are created without a filter (`CreateProjectV2ViewInput` has no filter
input) then updated with one — verified against the live schema.

## Expected empties

- **Current Sprint** is empty until issues are assigned a sprint. Correct on a
  fresh backlog.
- **Triage Queue** depends on the `status:needs-triage` **label**, a v2 namespace.
  Until that label ships, triage runs off the board **Status: Triage** column
  instead; the view filter will be flipped to `status:Triage` when the label
  lands. (Tracked with the v2 label rollout.)
- **Epic Roadmap** renders only once epics have Start/Target dates set.

## Changing the board

Edit `config/project.yml` in a PR, then run `pm-bootstrap-board.yml`. The
reconciler adds new fields/options and reports extras; it never deletes a field,
because a field holds every value ever set on every item and dropping it discards
them all irrecoverably. Remove a field by hand in the UI, deliberately, if you
really mean to.
