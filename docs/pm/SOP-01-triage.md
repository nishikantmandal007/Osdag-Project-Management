# SOP-01 — Triage

Triage turns a raw issue into one that can be planned. It is three decisions and
an owner. Target: clear the Triage Queue within the severity SLA
([SOP-02](SOP-02-bug-tiering.md)).

## When

Every new issue lands in **Status: Triage** (board workflow 5, once enabled per
[BOARD-SETUP](BOARD-SETUP.md)). Work the **Triage Queue** view oldest-first.

## The four decisions

1. **Type** — `type:bug`, `type:feature`, `type:task`, … One label. If it's a
   bug, keep reading; otherwise skip severity.
2. **Severity** — `sev:S1`…`S4`. Objective, "impact if never fixed." Set the
   board **Severity** field to match. This drives the SLA.
3. **Area** — one or more `area:*`. Most issues span two subsystems; add both.
   Mirror them into the board **Area** multi-select.
4. **Epic** — set the board **Epic** field to the outcome this belongs to. If it
   fits none, it is either genuinely out of scope (close with a reason) or a gap
   in the epic set (raise it in grooming).

Then set **Status: Ready** if it meets the Definition of Ready
([SOP-07](SOP-07-issue-lifecycle.md)), or leave it in Triage with a
`needs-repro` / `needs-info` note if it doesn't.

## Reproducibility gate

A bug with no reproduction is not Ready. Ask for: exact inputs, the design/bridge
type, OS, and what was expected vs. observed. Do not size or schedule an
unreproduced bug — it hides its own severity.

## What triage does *not* do

- It does not assign a **sprint** — that's grooming/planning ([SOP-03](SOP-03-sprint-cadence.md)).
- It does not set **priority** — priority is *when we schedule it*, decided at
  planning against capacity, not at intake.

## Note on issues opened via API

Issues created through `gh issue create` or the seeder bypass any issue-form
fields. Triage must not assume a template was filled in — read the body and fill
the gaps yourself.
