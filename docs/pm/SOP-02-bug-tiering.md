# SOP-02 — Bug tiering and SLAs

Severity is **impact if never fixed** — objective, set at intake. Priority is
**when we schedule it** — set at planning against capacity. They are different
axes; a S3 can be P1 if it blocks a demo, and a S1 is P0 by default but the two
are not the same field.

## Severity ladder

| Sev | Definition | Example | Default priority | Triage SLA | Fix SLA |
|---|---|---|---|---|---|
| **S1-critical** | Wrong structural output presented as correct; crash; release blocker | GUI shear ≠ report shear (#294) | P0-now | 1 business day | Current sprint |
| **S2-major** | Feature unusable or value unverifiable; workaround exists | Design fails on a valid dropdown value | P1-sprint | 2 business days | Current sprint |
| **S3-minor** | Incorrect display, no safety impact | Unit / precision loss | P2-next | 5 business days | Within 2 sprints |
| **S4-cosmetic** | Polish: hover, alignment, spacing | Toolbar highlight | P3-backlog | Next grooming | Unbounded |

**SLAs are business days on a volunteer team.** They are commitments to *look*,
not a paid on-call rotation. The point is that nothing critical sits unseen for a
week — not a four-hour pager promise nobody can keep.

## The one that matters

**S1 is reserved for wrong numbers shown as right.** A structural design tool that
confidently prints an incorrect capacity is worse than one that crashes, because
the crash is visible and the wrong number is not. When in doubt between S1 and
S2, ask: *could someone build to this output and be wrong?* If yes, it's S1.

## Setting it

- Label: `sev:S1-critical` … `sev:S4-cosmetic` (source of truth for the migration
  and metrics).
- Board **Severity** field: mirror it, so the board views and roadmap can filter.

The `sev:` label carries the SLA text in its description (`config/labels.yml`), so
it travels with the issue.
