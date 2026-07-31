# SOP-05 — Running the reconciler

The reconciler makes GitHub match `config/`. It **never deletes** — anything
present on GitHub but absent from config is *reported*, never removed, because a
label→issue association is unrecoverable once broken.

## Golden rule

**Dry-run is the default. You have to ask for mutations.** Every entry point
reports before it writes, and re-running after a successful apply is a no-op.
Idempotency is the property that makes promotion safe.

## The pieces

| Command / workflow | Reconciles | Notes |
|---|---|---|
| `python -m pm.reconcile --repo O/N --dry-run` | Labels | Exit 1 = drift found; exit 2 = config invalid |
| `python -m pm.bootstrap_board --owner L --repo O/N` | Board fields + views | `--apply` to write; `--populate` to backfill issues |
| `python -m pm.epics --repo O/N` | Epics + sub-epics | Marker-idempotent, report-only |
| `python -m pm.seed --repo O/N` | Upstream issues | One-way mirror; see [SOP-06](SOP-06-seeding-promotion.md) |

Locally use `python3` (this machine has no `python`). In Actions everything runs
with `GH_PM_TOKEN`, so the token never transits a laptop or chat.

## Reading a dry-run

```
python3 -m pm.reconcile --repo nishikantmandal007/osdagbridge-pm --dry-run
```

- `created` / `updated` / `renamed` — what an `--apply` *would* do.
- `extra 'X' (not in config; not deleted)` — GitHub has it, config doesn't. A
  human decides whether to add it to config or delete it in the UI. The
  reconciler will not.
- Exit **1** in dry-run means "drift pending," which is why the dry-run job shows
  a red X in Actions even when it succeeded. That is expected.

## The nightly

`pm-reconcile.yml` runs at **02:17 UTC daily**, always **read-only** — a
scheduled job that silently fixed things is how a board quietly diverges from
what people believe it is. If it finds drift it opens (or comments on) a single
**"Board drift detected"** issue with the log, and fails the run.

Untrusted content (issue titles, logs) is never interpolated into a `run:` block
— the drift log is read from a file. Keep it that way: this repo is public and
issue titles are attacker-controlled.

## The heartbeat and health check

Each run writes `.heartbeat` (a UTC timestamp), and the scheduled job **commits
it back to `main`**. That commit is the point: **a stale committed heartbeat is
itself drift** — it's how a *silently dead* reconciler becomes visible without
anyone thinking to open the Actions tab. If the nightly stops firing, the
timestamp in git stops advancing, and the next run that does fire alarms on it.
`.heartbeat` is the one run artifact that is tracked in git for exactly this
reason; the reports (`.drift-report.json`, `.health-report.json`) stay ignored
and are uploaded as CI artifacts instead.

The board-**health** check (`python -m pm.health --repo O/N`) runs first in the
nightly, *before* the heartbeat is overwritten, and produces two signals:

- **Liveness** — the heartbeat is older than one nightly cycle (36h) → the
  reconciler itself may be dead. This is the finding that watches the watcher.
- **Hygiene** — issues open past 30 days with no owner, no type/area, or a bug
  with no severity. Only *old* issues, so day-old triage items aren't nagged.

Findings drive a single self-healing **"Board health"** issue: edited in place
while unhealthy, **closed automatically** when the board recovers. It never
fails the build — stale issues are normal, not a CI error.

> **Documented limitation:** epic membership is a board *field*, not a label,
> until the v2 `epic:` namespace ships, so "no epic" cannot be seen from issue
> metadata and is not checked. Claiming to check it would false-positive on every
> issue. One line of `pm/health.py` enables it once `epic:` labels exist.

## Applying for real

Only two ways to mutate:

1. **Manual dispatch** of `pm-reconcile.yml` with **Apply** checked — a human is
   watching the output.
2. A local `--apply` run by someone with the token.

Never make the scheduled path apply.
