# SOP-03 — Sprint cadence

Two-week sprints, starting **Monday 2026-08-03**. The Sprint field is a Projects
V2 **iteration** field generated from the board schema in `config/base.yml` (`start_date`,
`duration_days: 14`) — the board owns the numbered iterations, replacing the old
"Sprint N:" title-prefix convention.

## Changing the sprint length or start

Sprint length is `duration_days` on the Sprint field in `config/base.yml`:

```yaml
- name: Sprint
  type: ITERATION
  duration_days: 14        # 7 = weekly, 15 = fortnight-plus
  start_date: "2026-08-03"
```

Change `duration_days` (e.g. `7` or `15`), PR it, and run **Bootstrap board**
(`pm-bootstrap-board.yml`). GitHub generates iterations *forward* from
`start_date`, so this reshapes future sprints. To also move where the numbering
begins — for a fresh demo, "start today" — run bootstrap with
`--sprint-start today` (or a specific `YYYY-MM-DD`) rather than editing
`start_date`; that's what a first setup on osdag-admin uses so sprint 1 begins on
the setup day ([SOP-10](SOP-10-osdag-admin-setup.md)). The step-by-step, plus the
manual-UI alternative (**Sprint** field → *Edit iterations*), is
[SOP-09 Tutorial 3](SOP-09-customizing.md).

## The weekly rhythm

| When | Ceremony | Output |
|---|---|---|
| Sprint start (Mon) | **Planning** | Ready issues pulled into the sprint; priority set against capacity |
| Mid-sprint | **Grooming** | Backlog items sized, split if XL, made Ready |
| Sprint end (Fri, wk 2) | **Review + retro** | Sprint report committed; carryover re-planned |

## Planning: pulling work in

1. Open **Backlog Grooming** (`no:sprint`, non-epic, open).
2. For each candidate: confirm it's **Ready** ([SOP-07](SOP-07-issue-lifecycle.md)),
   set **Size**, set **Priority**.
3. Assign the board **Sprint** field to the current iteration and an **owner**.
4. Stop when the sized points meet team capacity. Under-fill beats over-fill on a
   volunteer team.

Once issues carry a sprint, the **Current Sprint** view
(`sprint:@current -status:Done`) populates. Until then it is correctly empty —
that empty board on a fresh backlog is the system working, not a bug.

## Grooming: keeping the backlog plannable

- **Split anything Size XL** before it's eligible — an XL is a planning smell, not
  a work item.
- Ensure every groomed item has type, severity (if a bug), area, and an epic.
- Push stale, no-longer-relevant items to `Done`/closed with a reason rather than
  letting them rot; the nightly health check will flag >30-day-old orphans
  regardless (T11).

## Priority vs. sprint

Assigning a sprint says *we intend to do this now*. Priority orders work *within*
the sprint when capacity gets tight. P0-now preempts — if a P0 lands mid-sprint,
something planned gets bumped back to the backlog, explicitly, not silently
dropped.

## Sprint reports

`pm-sprint-report.yml` (T13) commits `docs/pm/reports/sprint-N.md` at each sprint
boundary. It guards against divide-by-zero on an empty sprint, so running it
before the first real sprint is harmless.
