# SOP-07 — Issue lifecycle: Ready and Done

An issue moves Backlog → Triage → Ready → In Progress → In Review → QA/Verify →
Done (with Blocked as a side state). Two gates matter: **Definition of Ready**
(can we start?) and **Definition of Done** (can we close?).

## Filing a good issue

Whatever the type, a good issue answers:

- **What** happened / is wanted, in one sentence in the title.
- **Repro** (for bugs): exact inputs, bridge/design type, OS, expected vs.
  observed. A screenshot of the wrong value beats a description of it.
- **Scope**: one problem per issue. "Several dock values are wrong" is an epic or
  six issues, not one.

Issues filed via `gh issue create` or the seeder skip any form — the body still
needs to carry this. Don't rely on template fields existing.

## Definition of Ready (gate into a sprint)

An issue is Ready when:

- [ ] Type set; severity set if it's a bug.
- [ ] At least one area.
- [ ] Assigned to an epic (or explicitly agreed as standalone).
- [ ] Reproducible, or the investigation itself is the scoped work (a `type:spike`).
- [ ] Small enough — Size ≤ L. An XL is split first.
- [ ] Acceptance is stated: how we'll know it's done.

Not Ready → it stays in Triage/Backlog with a `needs-repro` / `needs-info` note.
Don't pull unready work into a sprint; it stalls mid-sprint and skews the report.

## Definition of Done (gate to close)

Done means:

- [ ] Code merged behind the PR gate (CI green — pytest + ruff).
- [ ] For a bug: a **regression test** pins it, so it can't silently return.
- [ ] For a structural-value bug: a **verification case** with a hand-computed
      expected value (this is the E4 harness; a passing test that only asserts
      "no exception" does not close an S1).
- [ ] The issue's stated acceptance is met and checked.
- [ ] Docs updated if behaviour or interface changed.

Closing an issue as **not planned** is legitimate and is *excluded* from the
closure-ratio metric denominator — don't game the number by mass-closing.

## Blocked

Move to **Blocked** only with the blocker **named in the issue** (a dependency, a
decision, another issue number). A Blocked item with no named blocker is really
just unstarted — send it back to Ready.
