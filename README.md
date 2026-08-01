<img src="docs/assets/osdag-logo.png" alt="Osdag" height="72">

# Osdag Project Management

*A FOSSEE / IIT Bombay project.*

One project-management engine for the FOSSEE family of projects: declarative
board configuration, a reconciler that keeps GitHub matching that configuration,
and the SOPs that describe how work actually flows. The same engine drives a
board per project — **Osdag**, **OsdagBridge**, and more — from a shared base
plus one small per-project overlay.

Today it runs the **OsdagBridge** board; an **Osdag** overlay is staged next
(`config/software/osdag.yml`). Adding a project is a new file in
`config/software/`, not new code.

**This repo holds process, not application code.** Each project's Python lives in
its own code repo; nothing here imports it.

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
config/base.yml       Shared across every project — type:/sev: labels, board
                        fields and views.
config/software/*.yml  One overlay per project — its areas, epics, source
                        repo(s), board title. `--software NAME` merges base + overlay.
config/rollup.yml      The "All Projects" board that spans every project.
pm/                    Python reconciler. Reads config/, makes GitHub match it.
docs/pm/               README front door + SOP appendices + board setup checklist.
.github/               Issue forms, PR template, and the pm-* workflows.
tests/                 pytest for the reconciler itself.
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

New to project management, or onboarding an intern? Read the
**[PM Handbook (PDF)](docs/pm/handbook/osdagbridge-pm-handbook.pdf)** — a
start-from-zero guide to epics, sprints, and the board, including a step-by-step
board setup and the three open-source questions (tampering, intern access, and
whether the automations were necessary). Source and build script live in
[`docs/pm/handbook/`](docs/pm/handbook/).

**[`docs/pm/README.md`](docs/pm/README.md)** is the front door — the work-item
hierarchy, label taxonomy, board views, and the SOPs for triage, sprints, epics,
and operating the reconciler. If you're standing the board up on another repo,
read **[`docs/pm/BOARD-SETUP.md`](docs/pm/BOARD-SETUP.md)** first: five board
automations have no API and must be clicked by hand.

## Status

Board live (project #3, 77 issues, 10 epics + 6 sub-epics seeded). Reconciler
runs nightly, read-only, with a board-health check (liveness heartbeat + stale
un-triaged issues) that self-heals its own "Board health" issue. Docs and SOPs
landed. Config is now split base + per-project overlay (`--software`), and the
board title is set to plain **OsdagBridge** in config — the one-time live rename
(`pm.bootstrap_board --rename-from "OsdagBridge Delivery" --apply`, needs the
PAT) is pending. Still open: the analytics bots and governance sign-off
([`docs/pm/PROMOTION.md`](docs/pm/PROMOTION.md)). See the tracker for detail.
