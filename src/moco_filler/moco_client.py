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
from moco_filler.models import (
    EntryResult,
    Project,
    SubmissionBatch,
    SubmissionResult,
    Task,
)


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

    def bulk_create(self, batch: SubmissionBatch) -> SubmissionResult:
        """Send ``batch`` to ``POST /activities/bulk`` and return a per-row result.

        Outcome mapping (see ``data-model.md`` § ``SubmissionResult``
        construction rule and ``contracts/moco-http.md``):

        * 2xx + response is a list the same length as the request → each
          item maps to an ``EntryResult``. Items carrying an ``error``
          field become ``failed`` rows; otherwise they become ``created``.
        * 2xx with any other shape → every row inherits ``created``.
        * Non-2xx (except 401/403, which raise ``AuthError``) → every row
          inherits ``failed`` with a shared ``error_message`` derived from
          the upstream status and body.
        * Transport error (``requests.RequestException``) → every row
          ``failed`` with the exception message.

        ``bulk_create`` itself does not raise ``BulkTotalFailureError`` /
        ``BulkPartialFailureError`` — the CLI inspects the returned
        ``SubmissionResult`` and maps it to exit code 0 / 6 / 7.
        """
        payload = {
            "activities": [
                {
                    "date": entry.date.strftime("%Y-%m-%d"),
                    "project_id": batch.project_id,
                    "task_id": batch.task_id,
                    "seconds": entry.seconds,
                    "description": batch.description,
                    "billable": batch.billable,
                }
                for entry in batch.entries
            ]
        }

        try:
            response = self._session.post(
                f"{self._base_url}/activities/bulk",
                json=payload,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as exc:
            return self._all_failed(batch, f"Network error: {exc}")

        if response.status_code in (401, 403):
            raise AuthError(
                "Authentication failed: check your Moco API key."
            )

        return self._parse_bulk_response(response, batch)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _parse_bulk_response(
        self,
        response: "requests.Response",
        batch: SubmissionBatch,
    ) -> SubmissionResult:
        """Translate one bulk response into a SubmissionResult."""
        if response.ok:
            body = self._try_json(response)
            if (
                isinstance(body, list)
                and len(body) == len(batch.entries)
            ):
                return SubmissionResult(
                    entries=[
                        self._entry_result_from_row(entry, row)
                        for entry, row in zip(batch.entries, body)
                    ]
                )
            return SubmissionResult(
                entries=[
                    EntryResult(date=e.date, status="created")
                    for e in batch.entries
                ]
            )

        body_text = (response.text or "").strip()
        message = f"HTTP {response.status_code}"
        if body_text:
            message = f"{message}: {body_text[:200]}"
        return self._all_failed(batch, message)

    @staticmethod
    def _try_json(response: "requests.Response") -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    @staticmethod
    def _entry_result_from_row(entry, row: Any) -> EntryResult:
        if isinstance(row, dict) and row.get("error"):
            return EntryResult(
                date=entry.date,
                status="failed",
                error_message=str(row["error"]),
            )
        return EntryResult(date=entry.date, status="created")

    @staticmethod
    def _all_failed(
        batch: SubmissionBatch, message: str
    ) -> SubmissionResult:
        return SubmissionResult(
            entries=[
                EntryResult(
                    date=e.date,
                    status="failed",
                    error_message=message,
                )
                for e in batch.entries
            ]
        )

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
