<img src="../assets/osdag-logo.png" alt="Osdag" height="64">

# OsdagBridge — Project Management

*Part of **Osdag Project Management**, one engine over many FOSSEE-project boards.
A FOSSEE / IIT Bombay project.*

The front door **for the OsdagBridge board**. If you are filing an issue, running
a sprint, or operating the board, start here and follow the link to the relevant
SOP. Each project in the suite has its own board built from `config/base.yml` plus
its overlay in `config/software/`; this page describes OsdagBridge's.

**New here, or new to project management?** Read the
**[PM Handbook (PDF)](handbook/osdagbridge-pm-handbook.pdf)** first. It teaches
epics, sprints, and the board from zero, walks through standing the board up step
by step, and answers the three open-source questions (can outsiders tamper with
it, how interns join without repository access, were the automations necessary).
The SOPs below are the terse reference once you know the ropes.

The [top-level README](../../README.md) explains *why this repo exists*. This
document explains *how work flows through it*.

- **Board:** <https://github.com/users/nishikantmandal007/projects/3> — "OsdagBridge"
  (renamed in place from "OsdagBridge Delivery"; if the live rename is still
  pending it shows the old title until `project_management.bootstrap_board --rename-from` runs).
- **Config is the source of truth.** Labels, epics, board fields and views come
  from `config/base.yml` (shared) merged with `config/software/osdagbridge.yml`
  (this project's areas + epics). The reconciler makes GitHub match it; you change
  the board by changing config in a PR, not by clicking (with the one exception in
  [BOARD-SETUP](BOARD-SETUP.md)).

---

## Work-item hierarchy

| Level | Vehicle | Lifespan | Closes when |
|---|---|---|---|
| **L1 Release** | Milestone (`v1.0-GA`, `v1.1`, `v2.0`) | 1–2 quarters | All child epics done, artifact shipped |
| **L2 Epic** | Issue, `type:epic` | 1–3 months | Outcome achieved |
| **L3 Story / Bug / Task** | Issue, `type:*` | ≤ 1 sprint | Definition of Done met, merged |
| **L4 Sub-task** | Native sub-issue | ≤ 2 days | Checked off |

Every L3 issue should end up with: a **type**, a **severity** (if it's a bug), an
**area**, an **epic**, and — once planned — a **sprint**. See
[SOP-01 Triage](SOP-01-triage.md).

---

## Label taxonomy (v1)

Three namespaces ship at v1, so triage is three decisions, not eight. `type:`
and `sev:` are shared across the suite (`config/base.yml`); `area:` is
project-specific (`config/software/osdagbridge.yml`).

- **`type:`** — `epic` `feature` `story` `bug` `task` `chore` `spike` `docs` `test`
- **`sev:`** — `S1-critical` `S2-major` `S3-minor` `S4-cosmetic` (see [SOP-02](SOP-02-bug-tiering.md))
- **`area:`** — the subsystem, multi-valued (an issue routinely spans two). The 12
  UI areas are the upstream labels renamed in place; the rest are code-side.

`pri:` `size:` `epic:` `status:` `release:` are **v2** — staged until the
reconciler can infer them rather than asking a volunteer to pick them by hand.
On the board itself these already exist as *fields* (Priority, Size, Epic, …);
they're just not yet *labels*.

---

## The ten epics

| Epic | Outcome | Release |
|---|---|---|
| **E1** result-traceability (+6 sub-epics) | One value, one source; divergence fails a test | v1.0-GA |
| **E2** input-integrity | Inputs traceable, persist, reset cleanly | v1.0-GA |
| **E3** windows-stability | No segfaults / OOM across repeated runs | v1.0-GA |
| **E4** verification-harness | DDCL cases in pytest + coverage gate on `core/` | v1.0-GA |
| **E5** ci-quality-gates | PR gate (done in Phase 0) + lint + unified deps | v1.0-GA |
| **E6** release-ga | Reproducible conda pkg + installer, Win & Linux | v1.0-GA |
| **E7** reporting-boq | Report chapters, BOQ, IFC verified | v1.0-GA |
| **E8** cad-visualization | CAD and plots stay synced with inputs | v1.0-GA |
| **E9** docs-onboarding | Accurate README, guides, CONTRIBUTING, CODEOWNERS | v1.1 |
| **E10** architecture-debt | Break up god-objects; solvers real or deleted | v1.1 |

E1 splits into sub-epics by design-check family (flexure, shear, LTB, fatigue,
stiffeners, shear-connectors) because it maps to the largest slice of the
backlog and would otherwise blow past GitHub's 100-child ceiling. See
[SOP-04 Epics](SOP-04-epics.md).

---

## Board views

| View | Layout | Answers |
|---|---|---|
| **Current Sprint** | Board | What are we doing right now? (`sprint:@current -status:Done`) |
| **Triage Queue** | Table | What just came in and needs a decision? |
| **Backlog Grooming** | Table | What's unplanned and needs sizing? (`no:sprint`) |
| **Epic Roadmap** | Roadmap | How are the outcomes tracking over time? |
| **Release v1.0-GA** | Board | What's blocking the release? |
| **By Owner** | Board | Who's carrying what this sprint? |
| **Release pipeline** | Board | What's merged and where is it in the conda channels? (group by **Deploy stage**) |
| **Workload** | Board | Who's carrying the most this sprint? (group by **Assignees**) |

**Current Sprint is empty until you sprint-plan** — nothing is assigned to a
sprint on a fresh backlog. That is correct, not a bug. See
[SOP-03 Sprint cadence](SOP-03-sprint-cadence.md).

**Status vs Deploy stage — two axes.** **Status** is the dev flow and ends at
**Merged** (PR merged to the default branch). Once merged, an item's release
progress is tracked on the separate **Deploy stage** field
(`Dev → Test → Ready for Prod → In Production`, blank = not deployed), set by the
conda release pipeline (see [SOP-06](SOP-06-seeding-promotion.md) / epic E6).

---

## Cadence at a glance

- **2-week sprints**, starting Monday 2026-08-03.
- **Nightly reconcile** (02:17 UTC) checks the board against config, read-only,
  and opens a "Board drift detected" issue if they diverge.
- **Triage** within the SLA for the severity — 1 business day for S1, up to next
  grooming for S4.

---

## SOP index

| SOP | Topic |
|---|---|
| [SOP-01](SOP-01-triage.md) | Triage — turning a raw issue into a planned one |
| [SOP-02](SOP-02-bug-tiering.md) | Bug tiering and SLAs |
| [SOP-03](SOP-03-sprint-cadence.md) | Sprint planning, grooming, and the iteration field |
| [SOP-04](SOP-04-epics.md) | Epics, sub-epics, and rollup |
| [SOP-05](SOP-05-reconciler.md) | Running the reconciler and reading drift |
| [SOP-06](SOP-06-seeding-promotion.md) | Direct-from-repo intake and promoting to osdag-admin |
| [SOP-07](SOP-07-issue-lifecycle.md) | Filing a good issue; Definition of Ready / Done |
| [SOP-08](SOP-08-board-views.md) | Board fields and view filters reference |
| [SOP-09](SOP-09-customizing.md) | Customizing the board — manual UI *and* YAML, with tutorials |
| [SOP-10](SOP-10-osdag-admin-setup.md) | Standing the board up on osdag-admin, with access control |
| [SOP-11](SOP-11-release-pipeline.md) | conda 3-channel release pipeline (dev → test → main) + Deploy stage |
| [DEMO](DEMO.md) | **Stand up a live public board to show the team** |
| [BOARD-SETUP](BOARD-SETUP.md) | **The 5 manual clicks the API can't do** |
| [PROMOTION](PROMOTION.md) | Governance: moving the canonical tracker (unowned — T15) |
