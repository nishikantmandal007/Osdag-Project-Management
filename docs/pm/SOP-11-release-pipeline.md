# SOP-11 — conda 3-channel release pipeline

**Epic:** E6 release-ga. **Status:** designed, documented here; the workflow
template ships in [`templates/release.yml`](templates/release.yml), the board-update
step is not yet wired (see "Wiring the board update"). This is the release half of
the board's two axes — **Status** is the dev flow (ends at *Merged*); **Deploy
stage** is where a merged artifact sits in the release channels
([SOP-08](SOP-08-board-views.md)).

---

## The idea: build once, promote the same artifact

A conda package is built **once**, on merge, and then *relabelled* as it earns
trust — never rebuilt per stage. anaconda.org models this as **channel labels** on
one package: `dev`, `test`, `main`. Promotion is `anaconda copy --from-label X
--to-label Y`, which moves the identical build, so what your users install from
`main` is byte-for-byte what was tested on `test`.

The channels are declared **per project** in the overlay so each software can
release to its own org/labels:

```yaml
# config/software/osdagbridge.yml
conda_channels:
  dev:  "osdag/label/dev"
  test: "osdag/label/test"
  main: "osdag/label/main"
```

Users install a stage with, e.g., `conda install -c osdag/label/test osdag`.

---

## The three promotions

| Trigger (on the **code** repo) | conda action | Board **Deploy stage** |
|---|---|---|
| Merge to the default branch | build → `upload --label dev` | **Dev** |
| Push a `v*-rc*` tag | `copy --from-label dev --to-label test` | **Test** |
| *(human QA gate — see below)* | *(none)* | **Ready for Prod** |
| Publish a GitHub Release | `copy --from-label test --to-label main` | **In Production** |

Three of the four Deploy-stage options are set automatically. **Ready for Prod**
is deliberately **manual**: it means "the RC on `test` has been QA'd and we intend
to ship it." A lead sets it by hand on the board before cutting the GitHub Release,
so the field records a human decision, not just a pipeline event. Blank = not
deployed (still in the dev flow).

---

## Prerequisites

On the **code** repo (not the PM repo), two secrets:

- **`ANACONDA_TOKEN`** — an anaconda.org token with upload rights to the release
  org (`osdag`). Mint at anaconda.org → Settings → Access; scope to *Allow write
  access to the API site* and the specific org.
- **`GH_PM_TOKEN`** — the same fine-grained PAT class the reconciler uses
  ([SOP-05](SOP-05-reconciler.md)), with **Account → Projects: Read and write**, so
  the release job can move the board's Deploy stage. Store it on the code repo too
  (secrets don't cross repos).

Set them with:

```
gh secret set ANACONDA_TOKEN --repo osdag-admin/OsdagBridge
gh secret set GH_PM_TOKEN    --repo osdag-admin/OsdagBridge
```

---

## Installing the workflow

Copy [`templates/release.yml`](templates/release.yml) to `.github/workflows/release.yml`
on the code repo and fill the three `TODO`s:

1. **The recipe path** — where `conda build` finds `meta.yaml`
   (`packaging/conda/` in the template; use the repo's actual recipe dir).
2. **`PKG_SPEC`** — `osdag/PACKAGE/VERSION`, resolved from the tag/release for the
   `copy` steps.
3. **`scripts/set-deploy-stage.sh`** — the board-update step (below).

The template already follows the two hard security rules: least-privilege
`permissions:` (only `contents: read`; the board write uses `GH_PM_TOKEN`, not
`GITHUB_TOKEN`, which cannot write Projects V2 anyway), and **no
`${{ github.event.* }}` inside any `run:` block** — tag names and release titles
are attacker-controlled on a public repo, so they're passed via `env:`.

---

## Wiring the board update (not yet built)

Each promotion should move the Deploy stage on the board item for the shipped
work. The step is stubbed as `scripts/set-deploy-stage.sh` because it needs one
GraphQL mutation the engine doesn't expose yet:

```
updateProjectV2ItemFieldValue(input: {
  projectId: <board node id>,
  itemId:    <the board item for this issue/PR>,
  fieldId:   <the "Deploy stage" field id>,
  value:     { singleSelectOptionId: <option id for $DEPLOY_STAGE> }
})
```

To wire it, the script resolves the four ids (project, item, field, option) with
`GH_PM_TOKEN` and calls the mutation with `$DEPLOY_STAGE` from the job's `env:`.
The reconciler already fetches project/field/option ids
(`project_management/project.py`), so the intended home is a small
`project_management.set_deploy_stage --software NAME --item <id> --stage "Test"`
subcommand the workflow calls — tracked under **E6**. Until then the field is set
by hand, and the conda promotions still work on their own.

---

## Verify

- **A build lands on `dev`:** after a merge, `conda search -c osdag/label/dev
  osdag` shows the new build.
- **RC promotes to `test`:** `anaconda show osdag/osdag` lists the same build
  under the `test` label after the `v*-rc*` tag.
- **Release promotes to `main`:** the version installable with
  `conda install -c osdag osdag` matches the tested RC.
- **Board reflects it:** the **Release pipeline** view
  ([SOP-08](SOP-08-board-views.md), grouped by Deploy stage) shows the item under
  the expected column — once the board-update step is wired.
