# Board setup — the manual clicks

Almost the entire board is built and healed by config. **Five things are not**,
because GitHub exposes no create/update mutation for Projects V2 built-in
workflows — only `deleteProjectV2Workflow` and a read-only `workflows` field. The
reconciler therefore cannot provision or heal them, and **promotion to another
repo is not a single command**: whoever stands up the board on
`osdag-admin/OsdagBridge` will click through this list again.

Do these once, in the browser, on
**<https://github.com/users/nishikantmandal007/projects/3>**.

---

## Where these live

Open the board → **⋯** (top-right) → **Workflows**. Every item below is one of
the built-in workflows listed there. Each is **off by default**.

---

## 1. Auto-add items — one per source repo

**Why:** the board tracks its source repos' issues **in place** (see
[SOP-06](SOP-06-seeding-promotion.md)). Without Auto-add, only issues opened
*from now on* land on the board — and GitHub gives each Auto-add workflow a
single repo filter, so **you add one Auto-add per source repo** in the overlay's
`source_repos`. A project with two source repos needs two of these.

For each source repo:

- Workflows → **Auto-add to project** (use a fresh one per repo) → **Edit**
- **When:** an item is added to `OWNER/SOURCE-REPO` (filter: `is:issue`)
- **Set:** add the item to the project
- **Enable.**

> Open issues that already existed were backfilled once via the `--populate` run
> of `pm-bootstrap-board.yml`, which iterates every `source_repo`. Auto-add only
> catches *future* issues — backfill and Auto-add are complementary, not
> redundant.

## 2. Item closed → Status: Done

- Workflows → **Item closed** → **Edit**
- **When:** an issue or PR in the project is closed
- **Set:** Status → **Done**
- **Enable.**

## 3. Pull request merged → Status: Done

- Workflows → **Pull request merged** → **Edit**
- **When:** a PR linked to a project item is merged
- **Set:** Status → **Done**
- **Enable.**

## 4. Auto-archive items → Done after 14 days

**Why:** keeps the board readable; Done items older than a sprint drop out of the
active views but stay retrievable in the archive.

- Workflows → **Auto-archive items** → **Edit**
- **When:** Status is **Done** and the item hasn't been updated in **14 days**
- **Set:** archive the item
- **Enable.**

## 5. Item added → Status: Triage

**Why:** anything arriving on the board without a status starts in Triage, so it
shows up in the Triage Queue view and gets the [SOP-01](SOP-01-triage.md)
treatment instead of sitting in "No Status" forever.

- Workflows → **Item added to project** → **Edit**
- **When:** an item is added to the project
- **Set:** Status → **Triage**
- **Enable.**

---

## Verify

After enabling all five:

1. Open a throwaway test issue in **a source repo** → it should appear on the
   board within a few seconds, with **Status: Triage** (workflows 1 + 5).
2. Close it → **Status: Done** (workflow 2).
3. Delete the test issue.

If step 1 doesn't happen, the most common cause is that no Auto-add (workflow 1)
names *that* source repo — re-open the editors and confirm there is one Auto-add
per repo in the overlay's `source_repos`.

---

## Field automations that *are* config-driven

Do **not** try to set these here — they come from base.yml + the project's
`config/software/NAME.yml` overlay via the reconciler and will be overwritten:

- the Status column set and colours
- the Sprint iteration schedule
- every single-select / multi-select field option

The only board state that is genuinely click-only is the five workflows above.
