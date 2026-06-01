"""HTTP layer for the Moco activities API.

Implements the four endpoints documented in
``specs/001-moco-time-tracker/contracts/moco-http.md``. Every request
carries the ``Authorization: Token token=<API_KEY>`` header and a 15s
timeout per research.md §7. Failures are mapped to the domain
exceptions in ``errors.py`` so the CLI glue can translate exception
class → exit code via a single lookup.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import requests

from moco_filler.errors import AuthError, NoProjectsError
from moco_filler.models import Project, Task


DEFAULT_TIMEOUT = 15.0


class MocoClient:
    """Synchronous Moco API client.

    Constructed once per run with the resolved API token and the base
    URL. The token lives only in the ``Authorization`` header set on
    the underlying ``requests.Session`` — it never appears in argv, in
    log lines, or in any returned value.
    """

    def __init__(self, token: str, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Token token={token}",
                "Content-Type": "application/json",
            }
        )

    def get_session(self) -> int:
        """Return the authenticated user's ``id`` from ``GET /session``."""
        response = self._get("/session")
        return int(response.json()["id"])

    def get_projects_assigned(self) -> List[Project]:
        """Return every project the authenticated user can book against.

        Tasks are embedded under each project per
        ``contracts/moco-http.md`` so one round-trip populates both
        pickers in the CLI.

        Raises ``NoProjectsError`` (exit ``3``) when Moco returns an
        empty array — the user has no assignments and no further
        interaction is meaningful.
        """
        response = self._get("/projects/assigned")
        raw = response.json()
        if not raw:
            raise NoProjectsError(
                "No projects are assigned to your Moco account."
            )
        return [
            Project(
                id=int(project_data["id"]),
                name=str(project_data["name"]),
                tasks=[
                    Task(id=int(t["id"]), name=str(t["name"]))
                    for t in project_data.get("tasks", [])
                ],
            )
            for project_data in raw
        ]

    def get_activities(
        self,
        from_date: date,
        to_date: date,
        user_id: int,
    ) -> List[Dict[str, Any]]:
        """Return the user's existing activity records in the date range.

        Per the 2026-06-01 clarification embedded in
        ``contracts/moco-http.md`` § ``GET /activities``, we filter on
        the date range and ``user_id`` only — **no** ``project_id`` /
        ``task_id`` filter — so the planner can sum hours per date
        across every project the user has booked against (FR-012).
        """
        response = self._get(
            "/activities",
            params={
                "from": from_date.strftime("%Y-%m-%d"),
                "to": to_date.strftime("%Y-%m-%d"),
                "user_id": user_id,
            },
        )
        raw = response.json()
        return list(raw) if isinstance(raw, list) else []

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> "requests.Response":
        """GET ``path`` and map common error statuses to domain errors."""
        response = self._session.get(
            f"{self._base_url}{path}",
            params=params,
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code in (401, 403):
            raise AuthError(
                "Authentication failed: check your Moco API key."
            )
        response.raise_for_status()
        return response
