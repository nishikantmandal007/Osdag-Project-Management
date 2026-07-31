# osdagbridge-pm

Project-management system for [OsdagBridge](https://github.com/osdag-admin/OsdagBridge):
declarative board configuration, a reconciler that keeps GitHub matching that
configuration, and the SOPs that describe how work actually flows.

**This repo holds process, not application code.** OsdagBridge's Python lives in
the code repo; nothing here imports it.

## Why this repo exists separately

It is deliberately **not a fork**. GitHub disables scheduled workflows in forked
repositories, and the nightly reconciler plus the sprint report are the two
pieces that most need proving before any of this touches a real tracker.

It is also a **staging environment**. Everything here is written to be
repo-parameterised so the same configuration can be promoted to
`osdag-admin/OsdagBridge` once the process has been validated with real people
filing real issues.

## Layout

```
config/          Declarative source of truth — labels, epics, fields, views.
pm/              Python reconciler. Reads config/, makes GitHub match it.
docs/pm/         README front door + SOP appendices + board setup checklist.
.github/         Issue forms, PR template, and the pm-* workflows.
tests/           pytest for the reconciler itself.
```

## Ground rules

- **The reconciler never deletes.** It creates and updates; anything extra is
  reported in a drift issue for a human to remove deliberately. Label→issue
  associations are unrecoverable once broken, so that blast radius is designed
  out rather than guarded.
- **Config is reviewed like code.** Taxonomy changes go through a PR.
- **Some of the board cannot be automated.** GitHub exposes no create/update
  mutation for Projects V2 built-in workflows — only a delete and a read-only
  field. Those five automations are a manual checklist in
  `docs/pm/BOARD-SETUP.md`, not something the reconciler can provision or heal.
  Promotion is therefore not a single command, and the docs say so.

## Start here

**[`docs/pm/README.md`](docs/pm/README.md)** is the front door — the work-item
hierarchy, label taxonomy, board views, and the SOPs for triage, sprints, epics,
and operating the reconciler. If you're standing the board up on another repo,
read **[`docs/pm/BOARD-SETUP.md`](docs/pm/BOARD-SETUP.md)** first: five board
automations have no API and must be clicked by hand.

## Status

Board live (project #3, 77 issues, 10 epics + 6 sub-epics seeded). Reconciler
runs nightly, read-only, with a board-health check (liveness heartbeat + stale
un-triaged issues) that self-heals its own "Board health" issue. Docs and SOPs
landed. Still open: the analytics bots and governance sign-off
([`docs/pm/PROMOTION.md`](docs/pm/PROMOTION.md)). See the tracker for detail.
