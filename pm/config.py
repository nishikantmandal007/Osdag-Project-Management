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


def _load_yaml(path: Path) -> dict:
    """Read one YAML file into a dict, or raise a readable ConfigError."""
    if not path.is_file():
        raise ConfigError(f"missing config: {path}")
    try:
        return yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name} is not valid YAML: {exc}") from exc


def load_labels(path: Path | None = None) -> LabelConfig:
    """Load `config/labels.yml`.

    Flattens the namespace grouping into a single tuple, resolving each
    namespace's default colour. See `_labels_from_document` for the cross-checks.
    """
    path = path or (CONFIG_DIR / "labels.yml")
    return _labels_from_document(_load_yaml(path), source=path.name)


def _labels_from_document(document: dict, source: str = "labels") -> LabelConfig:
    """Validate an already-loaded labels document and build a `LabelConfig`.

    The document may come from a single `labels.yml` or from `load_merged`
    (base namespaces + the overlay's `area:` namespace) — either way it has the
    same shape and validates against the same schema. Cross-checks that the
    schema cannot express:

    - no duplicate label names
    - every label name carries its namespace prefix
    - no alias collides with a desired name, or with another alias
    - no desired label is also listed as protected
    """
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
        raise ConfigError(f"{source} is inconsistent:\n" + "\n".join(f"  {p}" for p in problems))

    return LabelConfig(
        labels=tuple(labels),
        protected=protected,
        migrations=dict(document.get("migrations", {})),
    )


@dataclass(frozen=True)
class SubEpic:
    slug: str
    title: str
    areas: tuple[str, ...] = ()


@dataclass(frozen=True)
class Epic:
    code: str
    title: str
    outcome: str
    release: str
    areas: tuple[str, ...] = ()
    sub_epics: tuple[SubEpic, ...] = ()


@dataclass(frozen=True)
class EpicConfig:
    marker_prefix: str
    epics: tuple[Epic, ...]


def load_epics(
    path: Path | None = None, known_labels: set[str] | None = None
) -> EpicConfig:
    """Load `config/epics.yml`. See `_epics_from_document` for the cross-checks."""
    path = path or (CONFIG_DIR / "epics.yml")
    return _epics_from_document(_load_yaml(path), known_labels=known_labels, source=path.name)


def _epics_from_document(
    document: dict, known_labels: set[str] | None = None, source: str = "epics"
) -> EpicConfig:
    """Validate an already-loaded epics document and build an `EpicConfig`.

    The document may come from a single `epics.yml` or from `load_merged` (the
    overlay's `epics.items`). Beyond the schema, cross-checks that:

    - epic codes are unique (they map 1:1 to the board's Epic field options),
    - sub-epic slugs are unique within their parent,
    - every referenced `area:` label actually exists (when `known_labels` is
      supplied) — a typo'd area would otherwise create an unlabelled epic.
    """
    _validate(document, "epics.schema.json")

    epics: list[Epic] = []
    problems: list[str] = []
    seen_codes: set[str] = set()

    for entry in document["epics"]:
        code = entry["code"]
        if code in seen_codes:
            problems.append(f"duplicate epic code: {code!r}")
        seen_codes.add(code)

        subs: list[SubEpic] = []
        seen_slugs: set[str] = set()
        for sub in entry.get("sub_epics", []):
            if sub["slug"] in seen_slugs:
                problems.append(f"{code}: duplicate sub-epic slug {sub['slug']!r}")
            seen_slugs.add(sub["slug"])
            subs.append(
                SubEpic(slug=sub["slug"], title=sub["title"], areas=tuple(sub.get("areas", [])))
            )

        epics.append(
            Epic(
                code=code,
                title=entry["title"],
                outcome=" ".join(entry["outcome"].split()),
                release=entry["release"],
                areas=tuple(entry.get("areas", [])),
                sub_epics=tuple(subs),
            )
        )

    if known_labels is not None:
        for epic in epics:
            for area in epic.areas:
                if area not in known_labels:
                    problems.append(f"{epic.code}: unknown area label {area!r}")
            for sub in epic.sub_epics:
                for area in sub.areas:
                    if area not in known_labels:
                        problems.append(f"{epic.code}/{sub.slug}: unknown area label {area!r}")

    if problems:
        raise ConfigError(f"{source} is inconsistent:\n" + "\n".join(f"  {p}" for p in problems))

    return EpicConfig(
        marker_prefix=document.get("marker_prefix", "epic"),
        epics=tuple(epics),
    )


@dataclass(frozen=True)
class SeedConfig:
    source_repo: str
    snapshot: Path
    label_map: dict[str, tuple[str, ...]]

    def map_labels(self, source_labels: list[str]) -> tuple[list[str], list[str]]:
        """Translate one issue's source labels to target labels.

        Returns (mapped_targets, unmapped_sources). A source label present in
        the map with an empty list is treated as intentionally-unmapped and does
        NOT appear in unmapped_sources; a source label absent from the map does.
        """
        targets: list[str] = []
        unmapped: list[str] = []
        for src in source_labels:
            if src in self.label_map:
                targets.extend(self.label_map[src])
            else:
                unmapped.append(src)
        # de-dupe, preserve order
        seen: set[str] = set()
        deduped = [t for t in targets if not (t in seen or seen.add(t))]
        return deduped, unmapped


def load_seed(
    path: Path | None = None, known_labels: set[str] | None = None
) -> SeedConfig:
    """Load `config/seed.yml`.

    Beyond the schema, checks every mapped *target* label exists (when
    `known_labels` is given) and that the snapshot file is present — both would
    otherwise fail deep inside a live seeding run.
    """
    path = path or (CONFIG_DIR / "seed.yml")
    if not path.is_file():
        raise ConfigError(f"missing config: {path}")

    try:
        document = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name} is not valid YAML: {exc}") from exc

    _validate(document, "seed.schema.json")

    label_map = {k: tuple(v) for k, v in document["label_map"].items()}
    snapshot = (REPO_ROOT / document["snapshot"]).resolve()

    problems: list[str] = []
    if not snapshot.is_file():
        problems.append(f"snapshot not found: {snapshot}")
    if known_labels is not None:
        for src, targets in label_map.items():
            for tgt in targets:
                if tgt not in known_labels:
                    problems.append(f"label_map[{src!r}] -> unknown target label {tgt!r}")
    if problems:
        raise ConfigError(f"{path.name} is inconsistent:\n" + "\n".join(f"  {p}" for p in problems))

    return SeedConfig(
        source_repo=document["source_repo"],
        snapshot=snapshot,
        label_map=label_map,
    )


# ── base + overlay merge ─────────────────────────────────────────────────────
# One engine runs several project boards. `config/base.yml` holds what is
# identical across them; `config/software/<name>.yml` holds what differs. This
# section merges the two back into the document shapes the single-file loaders
# already validate, so `--software <name>` reproduces a project's board exactly.

SOFTWARE_DIR = CONFIG_DIR / "software"


@dataclass(frozen=True)
class SoftwareConfig:
    """The overlay's non-label metadata: which board, repos, and channels."""

    name: str
    display_name: str
    short_description: str
    source_repos: tuple[str, ...]
    board_number: int | None = None
    logo: str | None = None
    conda_channels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MergedConfig:
    """base.yml + one overlay, resolved into the three things GitHub needs."""

    meta: SoftwareConfig
    labels: LabelConfig
    epics: EpicConfig
    board: dict  # project.yml-shaped: {version, project, fields, views}


def list_software() -> list[str]:
    """Names of every available overlay (`config/software/*.yml`), sorted."""
    if not SOFTWARE_DIR.is_dir():
        return []
    return sorted(p.stem for p in SOFTWARE_DIR.glob("*.yml"))


def _build_board(base: dict, overlay: dict, epics: EpicConfig) -> dict:
    """Assemble the project.yml-shaped board dict from base + overlay.

    The two `derived:` placeholders in `base["fields"]` are replaced in place
    (preserving field order) with options built from the overlay: one Epic
    option per epic `code`, and one Area option per `area:` label — UI areas
    (those with an `alias`) purple, code areas blue, matching the hand-written
    board this split replaces.
    """
    epic_options = [
        {"name": epic.code, "color": "PURPLE", "description": epic.title}
        for epic in epics.epics
    ]
    area_options = []
    for entry in overlay["area_labels"]["labels"]:
        short = entry["name"].split(":", 1)[1]
        color = "PURPLE" if entry.get("alias") else "BLUE"
        area_options.append(
            {"name": short, "color": color, "description": entry.get("description", "")}
        )

    fields: list[dict] = []
    for spec in base["fields"]:
        derived = spec.get("derived")
        if derived == "epic":
            fields.append({"name": spec["name"], "type": spec["type"], "options": epic_options})
        elif derived == "area":
            fields.append({"name": spec["name"], "type": spec["type"], "options": area_options})
        else:
            fields.append(spec)

    return {
        "version": base.get("version", 1),
        "project": {
            "title": overlay["display_name"],
            "short_description": overlay.get("short_description", ""),
        },
        "fields": fields,
        "views": base["views"],
    }


def load_merged(software: str) -> MergedConfig:
    """Merge `config/base.yml` with `config/software/<software>.yml`.

    Produces the same label/epic/board shapes the single-file loaders used to
    validate — so every existing schema and cross-check still runs, and
    `--software <name>` is a lossless stand-in for the old monolithic config.
    """
    base = _load_yaml(CONFIG_DIR / "base.yml")
    _validate(base, "base.schema.json")

    overlay_path = SOFTWARE_DIR / f"{software}.yml"
    if not overlay_path.is_file():
        available = ", ".join(list_software()) or "(none)"
        raise ConfigError(
            f"no overlay for software {software!r}: {overlay_path} not found. "
            f"Available: {available}"
        )
    overlay = _load_yaml(overlay_path)
    _validate(overlay, "software.schema.json")
    if overlay["name"] != software:
        raise ConfigError(
            f"{overlay_path.name}: name {overlay['name']!r} does not match its "
            f"filename {software!r}"
        )

    labels_doc = {
        "version": base.get("version", 1),
        "namespaces": {**base["namespaces"], "area": overlay["area_labels"]},
        "protected": base.get("protected", []),
        "migrations": overlay.get("migrations", {}),
    }
    labels = _labels_from_document(labels_doc, source=f"base.yml+{software}.yml")

    epics_doc = {
        "version": overlay.get("version", 1),
        "marker_prefix": overlay["epics"].get("marker_prefix", "epic"),
        "epics": overlay["epics"]["items"],
    }
    epics = _epics_from_document(
        epics_doc, known_labels=set(labels.by_name()), source=f"{software}.yml:epics"
    )

    board = _build_board(base, overlay, epics)

    meta = SoftwareConfig(
        name=overlay["name"],
        display_name=overlay["display_name"],
        short_description=overlay.get("short_description", ""),
        source_repos=tuple(overlay["source_repos"]),
        board_number=overlay.get("board_number"),
        logo=overlay.get("logo"),
        conda_channels=dict(overlay.get("conda_channels", {})),
    )

    return MergedConfig(meta=meta, labels=labels, epics=epics, board=board)


def load_rollup() -> dict:
    """Load and validate `config/rollup.yml` (the 'All Projects' board).

    Cross-checks that every rolled-up software name has a matching overlay, so a
    typo doesn't produce a Software option that points at nothing.
    """
    path = CONFIG_DIR / "rollup.yml"
    document = _load_yaml(path)
    _validate(document, "rollup.schema.json")
    available = set(list_software())
    missing = [name for name in document["software"] if name not in available]
    if missing:
        raise ConfigError(
            f"{path.name}: no overlay for software {missing!r} (have: "
            f"{', '.join(sorted(available)) or 'none'})"
        )
    return document
