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

- **No push access to upstream → no _Transfer issue_.** GitHub's native transfer
  (which preserves numbers and comment threads) requires write access to both
  repos. Without it, migration is **recreate-with-backlink**: new issue numbers,
  flattened comment history, and a period where two trackers are live and people
  may keep filing on the old one out of habit.
- **The 5 board workflows are manual clicks per repo** ([BOARD-SETUP](BOARD-SETUP.md)).
- The reconciler *config* replays with `--repo`/`--owner`; the *agreement* does not.

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

4. **What happens to the 59 upstream comment threads?**
   - Accept flattening into backlinks, or negotiate write access for a true
     transfer? _______________
   - How is the old tracker frozen so filing converges on the new one?
     _______________

## Sequence, once decided

1. Answers filled in above and agreed by the named contact.
2. Mint the promoted fine-grained PAT (account-level Projects: Read/Write),
   90-day expiry, store as `GH_PM_TOKEN` on the target repo.
3. Replay config: labels → board → epics → seed, each `--repo osdag-admin/OsdagBridge`,
   dry-run first, then apply.
4. Click the 5 board workflows ([BOARD-SETUP](BOARD-SETUP.md)) on the new board.
5. Freeze the old tracker (pin an issue pointing at the new one; consider locking).

Until step 1 has real names in it, do not start step 2.
