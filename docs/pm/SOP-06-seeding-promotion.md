# SOP-06 — Seeding and promotion

## Seeding

The seeder mirrors the open issues of an upstream repo into this one, once,
idempotently. Today's source is `Aditya-Donde/OsdagBridge` (59 issues → #19–#77).

### How it works

- **Reads a committed snapshot** (`config/seed-source.json`), not the live repo.
  This sidesteps the fine-grained PAT's cross-repo read limits and makes the seed
  **reviewable and reproducible** — the input is in git, not a moving target.
- Each mirrored issue gets an idempotency marker
  `<!-- src:Aditya-Donde/OsdagBridge#NNN -->`, so a re-run creates 0 and reports
  59 already-mirrored.
- A **backlink** line ("Mirrored from …#NNN") preserves provenance.
- Bodies have their bare `#NNN` cross-refs **rewritten** to the new numbers via
  `config/issue-map.yml` (source# → target#). The backlink and marker keep the
  *source* number on purpose and are never rewritten — if they were, idempotency
  would break.
- Upstream labels are translated through `config/seed.yml`'s `label_map`.
  "Check & Close" and "Future development" map to nothing (v2 namespaces).

### Refreshing the snapshot

The exact `gh` command to regenerate `config/seed-source.json` is in the header
of `config/seed.yml`. Refresh, commit, then re-run `pm-seed.yml`. Because the
seed is marker-idempotent, refreshing and re-running only *adds* new upstream
issues; it never duplicates existing mirrors.

### It is one-way

The seeder never edits or closes upstream. It is a mirror, not a sync.

---

## Promotion

Promotion means standing this system up on the real tracker
(`osdag-admin/OsdagBridge`) once it's validated here. **It is not one command** —
and the reasons are structural, not laziness:

1. **The 5 board workflows are manual** ([BOARD-SETUP](BOARD-SETUP.md)). Whoever
   promotes clicks through them again on the target board.
2. **The reconciler *config* is repo-parameterised** — `--repo` / `--owner` — so
   labels, epics, fields and views *do* replay with a different target. That part
   is one command per piece.
3. **Governance is unowned.** Without push access to the upstream repo, GitHub's
   *Transfer issue* is unavailable, so migration is recreate-with-backlink: new
   numbers, flattened comment threads, and a window where two trackers are live.
   Who owns the canonical tracker, and what happens to the 59 comment threads, is
   **[PROMOTION.md](PROMOTION.md)** (T15) — currently the real blocker, and
   currently unowned.

**Do not promote before PROMOTION.md names a contact and a decision.** Everything
technical is ready; the agreement is not.
