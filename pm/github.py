"""Thin GitHub REST client for the reconciler.

Deliberately small: list labels, create, update, rename. There is no delete
method and there should never be one — see :mod:`pm.plan`.

Auth comes from ``GH_PM_TOKEN`` (a fine-grained PAT), falling back to
``GITHUB_TOKEN``. Note that ``GITHUB_TOKEN`` is sufficient for labels but
**cannot** write Projects V2, so the board code will require the PAT.

Handles the secondary rate limit, which is the one that actually bites: GitHub
throttles content-creating requests to roughly 20/minute regardless of the
5000/hour primary budget, and answers with 403 plus ``Retry-After`` rather than
a 429.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from urllib.parse import quote

import requests

API = "https://api.github.com"
USER_AGENT = "osdagbridge-pm-reconciler"


class GitHubError(RuntimeError):
    pass


@dataclass
class Client:
    repo: str                       # "owner/name"
    token: str
    session: requests.Session | None = None
    max_retries: int = 5

    @classmethod
    def from_env(cls, repo: str) -> "Client":
        token = os.environ.get("GH_PM_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise GitHubError(
                "no token: set GH_PM_TOKEN (fine-grained PAT with Issues+Projects write). "
                "GITHUB_TOKEN works for labels but cannot write Projects V2."
            )
        return cls(repo=repo, token=token)

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": USER_AGENT,
                }
            )

    # ── transport ────────────────────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = path if path.startswith("http") else f"{API}{path}"

        for attempt in range(self.max_retries):
            response = self.session.request(method, url, timeout=30, **kwargs)

            if response.status_code < 400:
                return response

            # Secondary rate limit: 403 with Retry-After, or the primary budget
            # exhausted, which reports remaining=0 and a reset timestamp.
            retry_after = response.headers.get("Retry-After")
            exhausted = response.headers.get("X-RateLimit-Remaining") == "0"

            if response.status_code in (403, 429) and (retry_after or exhausted):
                if retry_after:
                    delay = float(retry_after)
                else:
                    reset = float(response.headers.get("X-RateLimit-Reset", 0))
                    delay = max(1.0, reset - time.time())
                delay = min(delay, 300.0)
                print(f"  rate limited; sleeping {delay:.0f}s (attempt {attempt + 1}/{self.max_retries})")
                time.sleep(delay)
                continue

            if response.status_code >= 500:
                delay = 2**attempt
                print(f"  {response.status_code} from GitHub; retrying in {delay}s")
                time.sleep(delay)
                continue

            raise GitHubError(f"{method} {url} -> {response.status_code}: {response.text[:300]}")

        raise GitHubError(f"{method} {url}: giving up after {self.max_retries} attempts")

    def _paginate(self, path: str) -> list[dict]:
        """Follow Link rel=next. Unpaginated reads silently truncate at 100."""
        items: list[dict] = []
        url = f"{API}{path}"
        while url:
            response = self._request("GET", url)
            items.extend(response.json())
            url = response.links.get("next", {}).get("url", "")
        return items

    # ── labels ───────────────────────────────────────────────────────────────

    def list_labels(self) -> list[dict]:
        return self._paginate(f"/repos/{self.repo}/labels?per_page=100")

    def create_label(self, name: str, color: str, description: str = "") -> dict:
        payload = {"name": name, "color": color, "description": description}
        return self._request("POST", f"/repos/{self.repo}/labels", json=payload).json()

    def update_label(
        self,
        name: str,
        color: str | None = None,
        description: str | None = None,
        new_name: str | None = None,
    ) -> dict:
        """Update in place. Passing ``new_name`` renames and keeps every issue
        association — which is why the planner never creates-and-deletes."""
        payload: dict = {}
        if new_name is not None:
            payload["new_name"] = new_name
        if color is not None:
            payload["color"] = color
        if description is not None:
            payload["description"] = description
        path = f"/repos/{self.repo}/labels/{quote(name, safe='')}"
        return self._request("PATCH", path, json=payload).json()

    # No delete_label(). Intentionally absent — deleting a label detaches it
    # from every issue that carried it, unrecoverably. Extras are reported.
