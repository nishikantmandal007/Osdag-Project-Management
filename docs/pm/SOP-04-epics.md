# SOP-04 — Epics and sub-epics

Epics are the L2 layer: outcome-level containers that close when the outcome is
achieved, not when a task is done. They are declarative — a project's
`config/software/NAME.yml:epics` is the source of truth and `pm/epics.py`
reconciles it.

## How an epic is defined

Each entry in the overlay's `epics:` list has:

- **`code`** — e.g. `E1 result-traceability`. Matches the board's Epic
  single-select option **verbatim**. Changing it orphans the board linkage.
- **`title`**, **`outcome`** — the outcome goes in the issue body.
- **`release`** — informational in the body; the actual milestone is set on the
  board.
- **`areas`** — label names that **must already exist** in the project's label
  set (the shared `type:/sev:` labels in `config/base.yml` plus the overlay's own
  `area:` labels). The reconciler refuses an unknown area rather than silently
  dropping it.

The reconciler writes an idempotency marker `<!-- pm-epic:KEY -->` into each epic
body, so re-running never duplicates one. It is **report-only** — it never closes
an epic, even one absent from config.

## Sub-epics (E1 only, for now)

E1 splits by design-check family — flexure, shear, LTB, fatigue, stiffeners,
shear-connectors — because it maps to the largest slice of the backlog and P1's
registry work will push a single epic past GitHub's **100-child ceiling**.

Sub-epics are linked as **native sub-issues** under the parent. The REST
`/sub_issues` endpoint wants the child's **`id`**, not its `number` — a 422 means
"already linked" and is swallowed as a no-op.

## Adding or changing an epic

1. Edit the overlay's `epics:` list in a PR (config is reviewed like code).
2. If you add an `areas` entry, make sure that `area:*` label exists in the
   overlay first, or the reconciler will reject it.
3. Nothing to sync by hand for the board: the **Epic** single-select options are
   *derived* from the epic codes at merge time, so a new epic becomes a board
   option automatically. Run `pm-bootstrap-board.yml` to apply the field change.
4. Merge, then run `pm-epics.yml` (manual dispatch). Idempotent: a second run
   reports 0 created / 0 linked.

## Rollup

`pm-epic-rollup.yml` (T13) recomputes progress on close/reopen and nightly. When
an issue moves from one epic to another it **recomputes both parents**, so
neither shows a stale count.

## Assigning issues to an epic

Set the board **Epic** field on the issue. When the `epic:` *label* namespace
ships in v2, that becomes the source of truth and the field is derived from it;
until then the field is set directly at triage.
