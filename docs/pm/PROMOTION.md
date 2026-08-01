# PROMOTION — governance for moving to the canonical tracker

> **Status: UNOWNED.** This is the real blocker. Everything technical is ready;
> the agreement is not. Promotion must not happen until the four decisions below
> have named answers. This document is a template for those answers, not a record
> that they've been made.

## What promotion is

Standing this PM system up on the canonical repo — `osdag-admin/OsdagBridge` —
and making it the single tracker students and contributors file against. Staging
proved the mechanics on `nishikantmandal007/osdagbridge-pm`; promotion is the
decision to make it real.

## Why it isn't a button

- **The PAT needs Issues + Projects write on the osdag-admin repos.** Direct-from-repo
  intake tracks issues *in place* on their own repos, and labels-as-code writes
  `type:/sev:/area:` onto them — so the promoted PAT needs **Issues: read + write**
  on each source repo and **Projects: read + write** on the account. That grant is
  the whole gate. (Good news: because issues stay in place there is **no** issue
  migration, no renumbering, and no flattened comment threads — the old mirror
  model's worst problem is gone. See [SOP-06](SOP-06-seeding-promotion.md).)
- **The 5 board workflows are manual clicks, one Auto-add per source repo**
  ([BOARD-SETUP](BOARD-SETUP.md)).
- The engine replays with `--software`/`--owner`; the *agreement* does not.

## The four decisions (each needs a named answer)

1. **Who is the osdag-admin contact?**
   - Name / handle: _______________
   - Have they said yes to hosting the board on `osdag-admin/OsdagBridge`? _______

2. **What does a "yes" look like?**
   - PAT ownership: whose account mints the promoted PAT, and what's its expiry?
     _______________
   - Collaborator access for the reconciler / assignees: _______________

3. **Who owns the canonical tracker after promotion?**
   - Single owner of triage + sprint cadence: _______________
   - What happens to `nishikantmandal007/osdagbridge-pm` — archived, or kept as
     staging? _______________

4. **Are the staging copies retired?**
   - Direct-from-repo means osdag-admin's issues are tracked *in place* — nothing
     is migrated. The only cleanup is the ~77 mirror-era copies on the staging
     board; decide whether to delete them or keep them as history
     ([SOP-06](SOP-06-seeding-promotion.md)). _______________
   - What happens to `nishikantmandal007/osdagbridge-pm` — archived, or kept as
     staging? _______________

## Sequence, once decided

The concrete, click-by-click runbook is **[SOP-10](SOP-10-osdag-admin-setup.md)**.
In brief:

1. Answers filled in above and agreed by the named contact.
2. Mint the promoted fine-grained PAT (account-level Projects: Read/Write; Issues:
   Read/Write on each source repo), 90-day expiry, store as `GH_PM_TOKEN`.
3. Point the overlay's `source_repos` at the osdag-admin repos; replay config with
   `--software`: board → epics → reconcile labels, dry-run first, then apply. Use
   `--sprint-start today` for the demo's first sprint.
4. Click the board workflows ([BOARD-SETUP](BOARD-SETUP.md)) — one Auto-add per
   source repo — and grant team leads project access ([SOP-10](SOP-10-osdag-admin-setup.md)).

Until step 1 has real names in it, do not start step 2.
