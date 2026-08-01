"""Diff desired config against live repo state and emit a plan.

Pure functions, no network. Everything here is decided from two plain inputs —
the desired :class:`~project_management.config.LabelConfig` and a snapshot of what the repo
currently has — so the whole decision surface is unit-testable and `--dry-run`
prints exactly what a real run would do.

**The reconciler never deletes.** A label on the repo but absent from config
becomes a :data:`Action.REPORT_EXTRA` entry in the drift report, for a human to
remove deliberately. Deleting a label silently detaches it from every issue that
carried it and GitHub keeps no record of the association, so the blast radius is
designed out rather than guarded with a threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .config import Label, LabelConfig


class Action(Enum):
    CREATE = "create"
    UPDATE = "update"          # same name, colour and/or description differ
    RENAME = "rename"          # alias found live; renamed in place
    REPORT_EXTRA = "report"    # present live, absent from config — never deleted
    NOOP = "noop"              # already matches


@dataclass(frozen=True)
class Step:
    action: Action
    name: str                    # desired name (or live name, for REPORT_EXTRA)
    from_name: str | None = None # RENAME only: the live name being renamed
    color: str | None = None
    description: str | None = None
    reason: str = ""

    def render(self) -> str:
        if self.action is Action.RENAME:
            return f"RENAME  {self.from_name!r} -> {self.name!r}  ({self.reason})"
        if self.action is Action.REPORT_EXTRA:
            return f"EXTRA   {self.name!r}  ({self.reason})"
        if self.action is Action.NOOP:
            return f"ok      {self.name!r}"
        return f"{self.action.value.upper():7} {self.name!r}  ({self.reason})"


@dataclass(frozen=True)
class Plan:
    steps: tuple[Step, ...]

    def of(self, *actions: Action) -> tuple[Step, ...]:
        return tuple(s for s in self.steps if s.action in actions)

    @property
    def mutations(self) -> tuple[Step, ...]:
        """Steps that change GitHub. REPORT_EXTRA and NOOP do not."""
        return self.of(Action.CREATE, Action.UPDATE, Action.RENAME)

    @property
    def is_clean(self) -> bool:
        """True when the repo already matches config.

        The idempotency property: reconcile twice, and the second plan is clean.
        Extras do not count as drift-to-fix, but they are still reported.
        """
        return not self.mutations

    def render(self) -> str:
        counts = {a: len(self.of(a)) for a in Action}
        header = (
            f"{counts[Action.CREATE]} create, "
            f"{counts[Action.UPDATE]} update, "
            f"{counts[Action.RENAME]} rename, "
            f"{counts[Action.REPORT_EXTRA]} extra (not deleted), "
            f"{counts[Action.NOOP]} already correct"
        )
        body = "\n".join(
            s.render() for s in self.steps if s.action is not Action.NOOP
        )
        return f"{header}\n{body}" if body else header


def _differs(desired: Label, live: dict) -> str | None:
    """Return a human reason if the live label needs updating, else None."""
    reasons = []
    live_color = str(live.get("color", "")).lstrip("#").lower()
    if live_color != desired.color.lower():
        reasons.append(f"colour {live_color or '?'} -> {desired.color}")
    live_desc = live.get("description") or ""
    if live_desc != desired.description:
        reasons.append("description")
    return ", ".join(reasons) or None


def plan_labels(config: LabelConfig, live_labels: list[dict]) -> Plan:
    """Build the label reconciliation plan.

    :param config: desired state, from ``load_merged(software).labels``.
    :param live_labels: raw GitHub label objects — needs ``name``, ``color``,
        ``description``.
    """
    live_by_name = {label["name"]: label for label in live_labels}
    aliases = config.aliases()
    steps: list[Step] = []

    # Names the plan accounts for, so anything left over is genuinely extra.
    claimed: set[str] = set()

    for desired in config.labels:
        live = live_by_name.get(desired.name)

        if live is None:
            # Not present under its new name — is it here under its old one?
            alias = desired.alias
            if alias and alias in live_by_name:
                claimed.add(alias)
                steps.append(
                    Step(
                        action=Action.RENAME,
                        name=desired.name,
                        from_name=alias,
                        color=desired.color,
                        description=desired.description,
                        reason="rename in place; preserves issue associations",
                    )
                )
                continue

            steps.append(
                Step(
                    action=Action.CREATE,
                    name=desired.name,
                    color=desired.color,
                    description=desired.description,
                    reason="absent",
                )
            )
            continue

        claimed.add(desired.name)
        reason = _differs(desired, live)
        if reason:
            steps.append(
                Step(
                    action=Action.UPDATE,
                    name=desired.name,
                    color=desired.color,
                    description=desired.description,
                    reason=reason,
                )
            )
        else:
            steps.append(Step(action=Action.NOOP, name=desired.name))

    # Anything live, unclaimed and unprotected is reported — never deleted.
    for name in sorted(live_by_name):
        if name in claimed or name in config.protected:
            continue
        reason = (
            "maps to " + repr(config.migrations[name]) + " but that label is not in config"
            if name in config.migrations
            else "not in config; remove by hand if unwanted"
        )
        steps.append(Step(action=Action.REPORT_EXTRA, name=name, reason=reason))

    return Plan(steps=tuple(steps))
