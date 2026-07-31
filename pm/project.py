"""Create and reconcile the Projects V2 board via GraphQL.

`gh project` at 2.45.0 cannot express this board: ``field-create`` accepts only
TEXT/SINGLE_SELECT/DATE/NUMBER (no ITERATION, no MULTI_SELECT) and there is no
view subcommand at all. Everything here goes through raw GraphQL, verified
against the live schema.

Two shapes worth knowing, both confirmed by introspection:

- ``CreateProjectV2ViewInput`` has **no** ``filter`` field; ``UpdateProjectV2ViewInput``
  does. Views are therefore created, then updated with their filter.
- Select-option inputs require ``color`` **and** ``description`` — both are
  non-null, so an empty description must still be sent.

Like the label reconciler, nothing here deletes. Fields and views that exist but
are absent from config are reported, never removed: a field carries every value
set on every item, and dropping it discards all of them irrecoverably.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import requests
import yaml

GRAPHQL = "https://api.github.com/graphql"

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class ProjectError(RuntimeError):
    pass


@dataclass
class GraphQL:
    token: str
    session: requests.Session = dc_field(default_factory=requests.Session)

    @classmethod
    def from_env(cls) -> "GraphQL":
        token = os.environ.get("GH_PM_TOKEN")
        if not token:
            raise ProjectError(
                "GH_PM_TOKEN is required. GITHUB_TOKEN cannot write Projects V2 — "
                "it has no Projects permission at all, regardless of workflow permissions."
            )
        return cls(token=token)

    def __call__(self, query: str, **variables):
        response = self.session.post(
            GRAPHQL,
            json={"query": query, "variables": variables},
            headers={
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "osdagbridge-pm-reconciler",
            },
            timeout=30,
        )
        if response.status_code >= 400:
            raise ProjectError(f"HTTP {response.status_code}: {response.text[:400]}")

        payload = response.json()
        if "errors" in payload:
            messages = "; ".join(e.get("message", str(e)) for e in payload["errors"])
            if "INSUFFICIENT_SCOPES" in response.text or "read:project" in messages:
                raise ProjectError(
                    f"token lacks Projects access: {messages}\n"
                    "A fine-grained PAT needs account permission 'Projects: Read and write'."
                )
            raise ProjectError(messages)
        return payload["data"]


def load_project_config(path: Path | None = None) -> dict:
    path = path or (CONFIG_DIR / "project.yml")
    if not path.is_file():
        raise ProjectError(f"missing config: {path}")
    return yaml.safe_load(path.read_text()) or {}


# ── lookups ──────────────────────────────────────────────────────────────────

def owner_id(gql: GraphQL, login: str) -> tuple[str, bool]:
    """Return (node id, is_organization) for a user or org login.

    Uses ``repositoryOwner``, which resolves either kind. Querying ``user`` and
    ``organization`` in one document looks tidier but makes GraphQL emit an
    error for whichever branch does not resolve, and a partial-error response is
    indistinguishable from a real failure.
    """
    data = gql(
        "query($login:String!){ repositoryOwner(login:$login){ id __typename } }",
        login=login,
    )
    owner = data.get("repositoryOwner")
    if not owner:
        raise ProjectError(f"no such user or organization: {login}")
    return owner["id"], owner["__typename"] == "Organization"


def find_project(gql: GraphQL, login: str, title: str, is_org: bool) -> dict | None:
    root = "organization" if is_org else "user"
    data = gql(
        f"""query($login:String!){{
              {root}(login:$login){{
                projectsV2(first:100){{ nodes{{ id number title }} }}
              }}
            }}""",
        login=login,
    )
    for node in data[root]["projectsV2"]["nodes"]:
        if node["title"] == title:
            return node
    return None


def project_fields(gql: GraphQL, project_id: str) -> dict[str, dict]:
    """Existing fields by name. Paginated — 100 is not a safe assumption."""
    fields: dict[str, dict] = {}
    cursor = None
    while True:
        data = gql(
            """query($id:ID!,$after:String){
                 node(id:$id){ ... on ProjectV2 {
                   fields(first:50, after:$after){
                     pageInfo{ hasNextPage endCursor }
                     nodes{
                       ... on ProjectV2FieldCommon { id name dataType }
                     }
                   }
                 }}
               }""",
            id=project_id,
            after=cursor,
        )
        page = data["node"]["fields"]
        for node in page["nodes"]:
            if node:
                fields[node["name"]] = node
        if not page["pageInfo"]["hasNextPage"]:
            return fields
        cursor = page["pageInfo"]["endCursor"]


def project_views(gql: GraphQL, project_id: str) -> dict[str, dict]:
    data = gql(
        """query($id:ID!){
             node(id:$id){ ... on ProjectV2 {
               views(first:50){ nodes{ id name number layout } }
             }}
           }""",
        id=project_id,
    )
    return {v["name"]: v for v in data["node"]["views"]["nodes"]}


# ── mutations ────────────────────────────────────────────────────────────────

def create_project(gql: GraphQL, owner: str, title: str, repo_id: str | None = None) -> dict:
    data = gql(
        """mutation($ownerId:ID!,$title:String!,$repositoryId:ID){
             createProjectV2(input:{ownerId:$ownerId,title:$title,repositoryId:$repositoryId}){
               projectV2{ id number title url }
             }
           }""",
        ownerId=owner,
        title=title,
        repositoryId=repo_id,
    )
    return data["createProjectV2"]["projectV2"]


def create_field(gql: GraphQL, project_id: str, spec: dict) -> dict:
    """Create one field. Handles all five dataTypes."""
    dtype = spec["type"]
    variables: dict = {"projectId": project_id, "name": spec["name"], "dataType": dtype}
    extra = ""

    if dtype in ("SINGLE_SELECT", "MULTI_SELECT"):
        key = "singleSelectOptions" if dtype == "SINGLE_SELECT" else "multiSelectOptions"
        # color and description are both non-null in the schema.
        variables[key] = [
            {
                "name": o["name"],
                "color": o.get("color", "GRAY"),
                "description": o.get("description", "") or "",
            }
            for o in spec["options"]
        ]
        arg = "[ProjectV2SingleSelectFieldOptionInput!]" if dtype == "SINGLE_SELECT" \
            else "[ProjectV2MultiSelectFieldOptionInput!]"
        extra = f", ${key}:{arg}"
        inner = f", {key}:${key}"
    elif dtype == "ITERATION":
        variables["iterationConfiguration"] = {
            "startDate": str(spec["start_date"]),
            "duration": int(spec.get("duration_days", 14)),
        }
        extra = ", $iterationConfiguration:ProjectV2IterationFieldConfigurationInput"
        inner = ", iterationConfiguration:$iterationConfiguration"
    else:
        inner = ""

    query = f"""mutation($projectId:ID!,$name:String!,$dataType:ProjectV2CustomFieldType!{extra}){{
                  createProjectV2Field(input:{{
                    projectId:$projectId, name:$name, dataType:$dataType{inner}
                  }}){{ projectV2Field{{ ... on ProjectV2FieldCommon {{ id name dataType }} }} }}
                }}"""
    return gql(query, **variables)["createProjectV2Field"]["projectV2Field"]


def create_view(gql: GraphQL, project_id: str, name: str, layout: str) -> dict:
    """Create a view. Filters cannot be set here — see update_view()."""
    data = gql(
        """mutation($projectId:ID!,$name:String!,$layout:ProjectV2ViewLayout!){
             createProjectV2View(input:{projectId:$projectId,name:$name,layout:$layout}){
               projectV2View{ id name number layout }
             }
           }""",
        projectId=project_id,
        name=name,
        layout=layout,
    )
    return data["createProjectV2View"]["projectV2View"]


def update_view(gql: GraphQL, view_id: str, filter_expr: str) -> dict:
    data = gql(
        """mutation($viewId:ID!,$filter:String){
             updateProjectV2View(input:{viewId:$viewId,filter:$filter}){
               projectV2View{ id name filter }
             }
           }""",
        viewId=view_id,
        filter=filter_expr,
    )
    return data["updateProjectV2View"]["projectV2View"]


def link_repository(gql: GraphQL, project_id: str, repo_id: str) -> None:
    gql(
        """mutation($projectId:ID!,$repositoryId:ID!){
             linkProjectV2ToRepository(input:{projectId:$projectId,repositoryId:$repositoryId}){
               repository{ id }
             }
           }""",
        projectId=project_id,
        repositoryId=repo_id,
    )


def repository_id(gql: GraphQL, owner: str, name: str) -> str:
    try:
        data = gql(
            "query($owner:String!,$name:String!){ repository(owner:$owner,name:$name){id} }",
            owner=owner,
            name=name,
        )
    except ProjectError as exc:
        if "Could not resolve to a Repository" in str(exc):
            raise ProjectError(_repo_invisible_help(gql, f"{owner}/{name}")) from exc
        raise
    if not data.get("repository"):
        raise ProjectError(_repo_invisible_help(gql, f"{owner}/{name}"))
    return data["repository"]["id"]


def _repo_invisible_help(gql: GraphQL, repo: str) -> str:
    """Turn 'Could not resolve to a Repository' into a specific remediation.

    The token authenticated fine (we resolved the owner), so this is almost
    always a fine-grained PAT that either does not list this repository under
    'Repository access', or lacks the Metadata permission that makes any repo
    resolvable at all.
    """
    try:
        viewer = gql("{ viewer { login } }")["viewer"]["login"]
    except ProjectError:
        viewer = "(unknown)"

    try:
        visible = gql(
            "{ viewer { repositories(first:20, affiliations:[OWNER]) { totalCount nodes { nameWithOwner } } } }"
        )["viewer"]["repositories"]
        names = ", ".join(n["nameWithOwner"] for n in visible["nodes"]) or "(none)"
        seen = f"{visible['totalCount']} repo(s) visible to this token: {names}"
    except ProjectError:
        seen = "could not list repositories visible to this token"

    return (
        f"token cannot see {repo}.\n"
        f"  authenticated as: {viewer}\n"
        f"  {seen}\n"
        "\n"
        "For a fine-grained PAT, check github.com/settings/personal-access-tokens:\n"
        f"  - 'Repository access' must explicitly include {repo}\n"
        "  - Repository permissions need at minimum: Metadata: Read-only\n"
        "    (Metadata is what makes a repository resolvable at all; selecting\n"
        "     Issues or Contents normally adds it, but it can be missed)\n"
        "  - Account permissions need: Projects: Read and write\n"
        "    (this one is account-level on user accounts, not per-repo)"
    )
