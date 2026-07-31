"""Tests for the reconciliation planner.

Two of these are load-bearing for the whole design:

``test_empty_config_never_deletes_anything``
    The prune guard. A truncated or badly-merged config must not be able to
    remove labels. Label->issue associations are unrecoverable.

``test_second_run_is_clean``
    Idempotency. Applying the plan and re-planning yields no mutations. This is
    what makes promotion to another repo safe: the same script can be re-run
    without accumulating changes.
"""

import pytest

from pm.config import Label, LabelConfig
from pm.plan import Action, plan_labels


def cfg(*labels, protected=(), migrations=None):
    return LabelConfig(
        labels=tuple(labels),
        protected=frozenset(protected),
        migrations=dict(migrations or {}),
    )


def live(name, color="cccccc", description=""):
    """A GitHub label object, as the API returns it."""
    return {"name": name, "color": color, "description": description}


def apply(plan, live_labels):
    """Simulate GitHub applying the plan, returning the new live state.

    Mirrors the executor: create adds, update overwrites, rename replaces the
    old entry in place, extras are untouched.
    """
    by_name = {label["name"]: dict(label) for label in live_labels}
    for step in plan.steps:
        if step.action is Action.CREATE:
            by_name[step.name] = live(step.name, step.color, step.description or "")
        elif step.action is Action.UPDATE:
            by_name[step.name] = live(step.name, step.color, step.description or "")
        elif step.action is Action.RENAME:
            by_name.pop(step.from_name, None)
            by_name[step.name] = live(step.name, step.color, step.description or "")
    return list(by_name.values())


class TestPruneGuard:
    """The reconciler must never delete. This is the irreversible direction."""

    def test_empty_config_never_deletes_anything(self):
        existing = [live("type:bug"), live("sev:S1-critical"), live("area:docs")]
        plan = plan_labels(cfg(), existing)

        assert plan.mutations == ()
        assert {s.name for s in plan.of(Action.REPORT_EXTRA)} == {
            "type:bug",
            "sev:S1-critical",
            "area:docs",
        }
        # No action in the entire vocabulary can remove a label.
        assert not any(a.value == "delete" for a in Action)

    def test_extras_are_reported_not_mutated(self):
        plan = plan_labels(cfg(Label("type:bug", "1d76db")), [live("wibble")])
        extras = plan.of(Action.REPORT_EXTRA)
        assert [s.name for s in extras] == ["wibble"]
        assert extras[0] not in plan.mutations

    def test_protected_labels_are_not_even_reported(self):
        """GitHub defaults and third-party labels stay invisible to the drift report."""
        plan = plan_labels(
            cfg(Label("type:bug", "1d76db"), protected=["bug", "dependencies"]),
            [live("bug"), live("dependencies"), live("stray")],
        )
        assert [s.name for s in plan.of(Action.REPORT_EXTRA)] == ["stray"]


class TestCreateAndUpdate:
    def test_absent_label_is_created(self):
        plan = plan_labels(cfg(Label("type:bug", "1d76db", "Something is wrong")), [])
        (step,) = plan.of(Action.CREATE)
        assert step.name == "type:bug"
        assert step.color == "1d76db"
        assert step.description == "Something is wrong"

    def test_colour_drift_is_updated(self):
        plan = plan_labels(
            cfg(Label("type:bug", "1d76db")), [live("type:bug", color="ff0000")]
        )
        (step,) = plan.of(Action.UPDATE)
        assert "ff0000 -> 1d76db" in step.reason

    def test_description_drift_is_updated(self):
        plan = plan_labels(
            cfg(Label("type:bug", "1d76db", "New wording")),
            [live("type:bug", color="1d76db", description="Old wording")],
        )
        assert "description" in plan.of(Action.UPDATE)[0].reason

    def test_matching_label_is_noop(self):
        plan = plan_labels(
            cfg(Label("type:bug", "1d76db", "Same")),
            [live("type:bug", color="1d76db", description="Same")],
        )
        assert plan.of(Action.NOOP)[0].name == "type:bug"
        assert plan.is_clean

    def test_live_colour_hash_prefix_is_tolerated(self):
        """GitHub returns bare hex, but a hand-edited config may carry '#'."""
        plan = plan_labels(
            cfg(Label("type:bug", "1d76db")), [live("type:bug", color="#1D76DB")]
        )
        assert plan.is_clean


class TestRename:
    """Renaming preserves issue associations; create-and-delete would orphan them."""

    def test_alias_present_live_is_renamed_not_recreated(self):
        plan = plan_labels(
            cfg(Label("area:girder-results", "c5b8e6", alias="Girder Results")),
            [live("Girder Results", color="c5b8e6")],
        )
        (step,) = plan.of(Action.RENAME)
        assert step.from_name == "Girder Results"
        assert step.name == "area:girder-results"
        assert plan.of(Action.CREATE) == ()
        # The old name must not also be flagged as an extra to remove.
        assert plan.of(Action.REPORT_EXTRA) == ()

    def test_alias_absent_falls_back_to_create(self):
        plan = plan_labels(
            cfg(Label("area:girder-results", "c5b8e6", alias="Girder Results")), []
        )
        assert plan.of(Action.CREATE)[0].name == "area:girder-results"
        assert plan.of(Action.RENAME) == ()

    def test_new_name_already_present_wins_over_alias(self):
        """A previous run already renamed it; do not rename twice."""
        plan = plan_labels(
            cfg(Label("area:girder-results", "c5b8e6", alias="Girder Results")),
            [live("area:girder-results", color="c5b8e6")],
        )
        assert plan.of(Action.RENAME) == ()
        assert plan.is_clean


class TestIdempotency:
    """Re-running must be a no-op. This is what makes promotion safe."""

    @pytest.fixture
    def config(self):
        return cfg(
            Label("type:bug", "1d76db", "Something behaves incorrectly"),
            Label("sev:S1-critical", "b60205", "Release blocker"),
            Label("area:girder-results", "c5b8e6", alias="Girder Results"),
        )

    def test_second_run_is_clean(self, config):
        state = [live("Girder Results", color="aaaaaa")]

        first = plan_labels(config, state)
        assert not first.is_clean

        state = apply(first, state)
        second = plan_labels(config, state)

        assert second.is_clean, second.render()
        assert len(second.of(Action.NOOP)) == 3

    def test_third_run_also_clean(self, config):
        """Guards against a plan that oscillates between two states."""
        state = []
        for _ in range(3):
            plan = plan_labels(config, state)
            state = apply(plan, state)
        assert plan_labels(config, state).is_clean


class TestRendering:
    def test_render_names_every_mutation(self):
        plan = plan_labels(
            cfg(Label("type:bug", "1d76db"), Label("type:task", "1d76db")),
            [live("type:bug", color="ff0000"), live("junk")],
        )
        out = plan.render()
        assert "1 create" in out and "1 update" in out and "1 extra (not deleted)" in out
        assert "type:task" in out and "junk" in out

    def test_noops_are_summarised_not_listed(self):
        plan = plan_labels(cfg(Label("type:bug", "1d76db")), [live("type:bug", "1d76db")])
        out = plan.render()
        assert "1 already correct" in out
        assert "ok      'type:bug'" not in out
