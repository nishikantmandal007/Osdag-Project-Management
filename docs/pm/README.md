# OsdagBridge — Project Management

The front door. If you are filing an issue, running a sprint, or operating the
board, start here and follow the link to the relevant SOP.

The [top-level README](../../README.md) explains *why this repo exists*. This
document explains *how work flows through it*.

- **Board:** <https://github.com/users/nishikantmandal007/projects/3> — "OsdagBridge Delivery"
- **Config is the source of truth.** Labels, epics, board fields and views all
  come from `config/*.yml`. The reconciler makes GitHub match it; you change the
  board by changing config in a PR, not by clicking (with the one exception in
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

Three namespaces ship at v1, so triage is three decisions, not eight. Full list
lives in `config/labels.yml`.

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

**Current Sprint is empty until you sprint-plan** — nothing is assigned to a
sprint on a freshly seeded backlog. That is correct, not a bug. See
[SOP-03 Sprint cadence](SOP-03-sprint-cadence.md).

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
| [SOP-06](SOP-06-seeding-promotion.md) | Seeding from upstream and promoting to osdag-admin |
| [SOP-07](SOP-07-issue-lifecycle.md) | Filing a good issue; Definition of Ready / Done |
| [SOP-08](SOP-08-board-views.md) | Board fields and view filters reference |
| [BOARD-SETUP](BOARD-SETUP.md) | **The 5 manual clicks the API can't do** |
| [PROMOTION](PROMOTION.md) | Governance: moving the canonical tracker (unowned — T15) |
