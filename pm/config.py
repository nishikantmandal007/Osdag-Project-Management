"""Load and validate `config/*.yml` before anything touches GitHub.

A malformed config must fail here, locally, with a readable message — not
halfway through mutating a live tracker. Every loader validates against the
matching JSON Schema in `config/schema/` and then applies the cross-checks a
schema cannot express (duplicate names, namespace prefix agreement, alias
collisions).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
SCHEMA_DIR = CONFIG_DIR / "schema"


class ConfigError(Exception):
    """Config is unusable. Raised before any network call."""


@dataclass(frozen=True)
class Label:
    """One desired label. `alias` is the former name, renamed in place."""

    name: str
    color: str
    description: str = ""
    alias: str | None = None

    @property
    def namespace(self) -> str | None:
        return self.name.split(":", 1)[0] if ":" in self.name else None


@dataclass(frozen=True)
class LabelConfig:
    labels: tuple[Label, ...]
    protected: frozenset[str] = frozenset()
    migrations: dict[str, str] = field(default_factory=dict)

    def by_name(self) -> dict[str, Label]:
        return {label.name: label for label in self.labels}

    def aliases(self) -> dict[str, Label]:
        """Former name -> desired label, for rename-in-place."""
        return {label.alias: label for label in self.labels if label.alias}


def _validate(document: dict, schema_name: str) -> None:
    """Raise ConfigError listing *every* schema violation, not just the first."""
    schema_path = SCHEMA_DIR / schema_name
    if not schema_path.is_file():
        raise ConfigError(f"missing schema: {schema_path}")

    validator = Draft202012Validator(json.loads(schema_path.read_text()))
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.path))
    if not errors:
        return

    lines = []
    for err in errors:
        where = "/".join(str(p) for p in err.path) or "(root)"
        lines.append(f"  {where}: {err.message}")
    raise ConfigError(f"{schema_name} validation failed:\n" + "\n".join(lines))


def load_labels(path: Path | None = None) -> LabelConfig:
    """Load `config/labels.yml`.

    Flattens the namespace grouping into a single tuple, resolving each
    namespace's default colour. Cross-checks that the schema cannot express:

    - no duplicate label names
    - every label name carries its namespace prefix
    - no alias collides with a desired name, or with another alias
    - no desired label is also listed as protected
    """
    path = path or (CONFIG_DIR / "labels.yml")
    if not path.is_file():
        raise ConfigError(f"missing config: {path}")

    try:
        document = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name} is not valid YAML: {exc}") from exc

    _validate(document, "labels.schema.json")

    labels: list[Label] = []
    problems: list[str] = []

    for namespace, spec in document["namespaces"].items():
        default_color = spec.get("color")
        for entry in spec["labels"]:
            name = entry["name"]
            if not name.startswith(f"{namespace}:"):
                problems.append(f"{name!r} is under namespace {namespace!r} but lacks the '{namespace}:' prefix")
            color = entry.get("color", default_color)
            if not color:
                problems.append(f"{name!r} has no colour and namespace {namespace!r} sets no default")
                color = "cccccc"
            labels.append(
                Label(
                    name=name,
                    color=color.lower(),
                    description=entry.get("description", ""),
                    alias=entry.get("alias"),
                )
            )

    seen: set[str] = set()
    for label in labels:
        if label.name in seen:
            problems.append(f"duplicate label name: {label.name!r}")
        seen.add(label.name)

    alias_owner: dict[str, str] = {}
    for label in labels:
        if not label.alias:
            continue
        if label.alias in seen:
            problems.append(f"alias {label.alias!r} on {label.name!r} collides with a desired label name")
        if label.alias in alias_owner:
            problems.append(f"alias {label.alias!r} claimed by both {alias_owner[label.alias]!r} and {label.name!r}")
        alias_owner[label.alias] = label.name

    protected = frozenset(document.get("protected", []))
    for clash in sorted(protected & seen):
        problems.append(f"{clash!r} is both a desired label and protected; pick one")

    if problems:
        raise ConfigError(f"{path.name} is inconsistent:\n" + "\n".join(f"  {p}" for p in problems))

    return LabelConfig(
        labels=tuple(labels),
        protected=protected,
        migrations=dict(document.get("migrations", {})),
    )
