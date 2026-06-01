"""Unit tests for moco_filler.moco_client — see contracts/moco-http.md.

Each Moco endpoint is mocked via the ``responses`` library. We assert
both the *shape* of the request we send (URL, headers, query params,
body) and how we map the response back to domain dataclasses, plus the
error → exception mapping.
"""

from __future__ import annotations

from datetime import date
from urllib.parse import parse_qs, urlparse

import pytest
import responses

from datetime import date as _date
from decimal import Decimal

from moco_filler.errors import AuthError, NoProjectsError
from moco_filler.moco_client import MocoClient
from moco_filler.models import (
    PlannedEntry,
    Project,
    SubmissionBatch,
    Task,
)


BASE_URL = "https://example.com/api/v1"
TOKEN = "test-token-deadbeef"
USER_ID = 12345


@pytest.fixture
def client() -> MocoClient:
    return MocoClient(token=TOKEN, base_url=BASE_URL)


# ---------- GET /session ----------


@responses.activate
def test_get_session_returns_user_id_on_2xx(client: MocoClient) -> None:
    responses.add(
        responses.GET,
        f"{BASE_URL}/session",
        json={"id": USER_ID, "firstname": "A", "lastname": "B"},
        status=200,
    )
    assert client.get_session() == USER_ID


@responses.activate
def test_get_session_sends_token_header(client: MocoClient) -> None:
    responses.add(
        responses.GET,
        f"{BASE_URL}/session",
        json={"id": USER_ID},
        status=200,
    )
    client.get_session()
    sent = responses.calls[0].request
    assert sent.headers["Authorization"] == f"Token token={TOKEN}"


@responses.activate
@pytest.mark.parametrize("status", [401, 403])
def test_get_session_raises_auth_error_on_401_or_403(
    client: MocoClient, status: int
) -> None:
    responses.add(
        responses.GET,
        f"{BASE_URL}/session",
        json={"error": "unauthorized"},
        status=status,
    )
    with pytest.raises(AuthError):
        client.get_session()


@responses.activate
def test_get_session_propagates_other_http_errors(
    client: MocoClient,
) -> None:
    responses.add(
        responses.GET,
        f"{BASE_URL}/session",
        json={"error": "boom"},
        status=500,
    )
    with pytest.raises(Exception):
        client.get_session()


def test_constructor_strips_trailing_slash_from_base_url() -> None:
    c = MocoClient(token=TOKEN, base_url=BASE_URL + "/")
    assert c._base_url == BASE_URL  # type: ignore[attr-defined]


# ---------- GET /projects/assigned ----------


_PROJECTS_PAYLOAD = [
    {
        "id": 123,
        "name": "Internal",
        "tasks": [
            {"id": 456, "name": "Administration"},
            {"id": 457, "name": "Meetings"},
        ],
    },
    {
        "id": 124,
        "name": "External",
        "tasks": [{"id": 458, "name": "Delivery"}],
    },
]


@responses.activate
def test_get_projects_assigned_maps_response_to_dataclasses(
    client: MocoClient,
) -> None:
    responses.add(
        responses.GET,
        f"{BASE_URL}/projects/assigned",
        json=_PROJECTS_PAYLOAD,
        status=200,
    )
    projects = client.get_projects_assigned()
    assert projects == [
        Project(
            id=123,
            name="Internal",
            tasks=[
                Task(id=456, name="Administration"),
                Task(id=457, name="Meetings"),
            ],
        ),
        Project(
            id=124,
            name="External",
            tasks=[Task(id=458, name="Delivery")],
        ),
    ]


@responses.activate
def test_get_projects_assigned_raises_no_projects_on_empty_array(
    client: MocoClient,
) -> None:
    responses.add(
        responses.GET,
        f"{BASE_URL}/projects/assigned",
        json=[],
        status=200,
    )
    with pytest.raises(NoProjectsError):
        client.get_projects_assigned()


@responses.activate
def test_get_projects_assigned_tolerates_missing_tasks_key(
    client: MocoClient,
) -> None:
    responses.add(
        responses.GET,
        f"{BASE_URL}/projects/assigned",
        json=[{"id": 1, "name": "P"}],
        status=200,
    )
    projects = client.get_projects_assigned()
    assert projects == [Project(id=1, name="P", tasks=[])]


@responses.activate
@pytest.mark.parametrize("status", [401, 403])
def test_get_projects_assigned_raises_auth_error_on_401_or_403(
    client: MocoClient, status: int
) -> None:
    responses.add(
        responses.GET,
        f"{BASE_URL}/projects/assigned",
        json={"error": "x"},
        status=status,
    )
    with pytest.raises(AuthError):
        client.get_projects_assigned()


# ---------- GET /activities ----------


_ACTIVITIES_PAYLOAD = [
    {"date": "2026-06-03", "hours": 4.0},
    {"date": "2026-06-04", "hours": 2.5},
]


@responses.activate
def test_get_activities_returns_raw_list(client: MocoClient) -> None:
    responses.add(
        responses.GET,
        f"{BASE_URL}/activities",
        json=_ACTIVITIES_PAYLOAD,
        status=200,
    )
    result = client.get_activities(
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 30),
        user_id=USER_ID,
    )
    assert result == _ACTIVITIES_PAYLOAD


@responses.activate
def test_get_activities_sends_only_date_range_and_user_id_params(
    client: MocoClient,
) -> None:
    """Q4 clarification: NO project_id / task_id filter on this endpoint."""
    responses.add(
        responses.GET,
        f"{BASE_URL}/activities",
        json=[],
        status=200,
    )
    client.get_activities(
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 30),
        user_id=USER_ID,
    )
    sent_url = responses.calls[0].request.url
    params = parse_qs(urlparse(sent_url).query)
    assert set(params.keys()) == {"from", "to", "user_id"}
    assert params["from"] == ["2026-06-01"]
    assert params["to"] == ["2026-06-30"]
    assert params["user_id"] == [str(USER_ID)]
    assert "project_id" not in params
    assert "task_id" not in params


@responses.activate
def test_get_activities_returns_empty_list_when_no_records(
    client: MocoClient,
) -> None:
    responses.add(
        responses.GET,
        f"{BASE_URL}/activities",
        json=[],
        status=200,
    )
    result = client.get_activities(
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 30),
        user_id=USER_ID,
    )
    assert result == []


@responses.activate
@pytest.mark.parametrize("status", [401, 403])
def test_get_activities_raises_auth_error_on_401_or_403(
    client: MocoClient, status: int
) -> None:
    responses.add(
        responses.GET,
        f"{BASE_URL}/activities",
        json={"error": "x"},
        status=status,
    )
    with pytest.raises(AuthError):
        client.get_activities(
            from_date=date(2026, 6, 1),
            to_date=date(2026, 6, 30),
            user_id=USER_ID,
        )


# ---------- POST /activities/bulk ----------


def _planned_entry(d: _date, hours: str = "8") -> PlannedEntry:
    return PlannedEntry(
        date=d,
        weekday=d.strftime("%a"),
        existing_hours_total=Decimal("0"),
        hours=Decimal(hours),
        included=True,
        already_logged=False,
    )


def _batch(entries) -> SubmissionBatch:
    return SubmissionBatch(
        project_id=123,
        task_id=456,
        description="Administration",
        billable=False,
        entries=entries,
    )


@responses.activate
def test_bulk_create_sends_serialized_payload(client: MocoClient) -> None:
    entries = [
        _planned_entry(_date(2026, 6, 1)),
        _planned_entry(_date(2026, 6, 2), hours="4.5"),
    ]
    responses.add(
        responses.POST,
        f"{BASE_URL}/activities/bulk",
        json={},
        status=200,
    )
    client.bulk_create(_batch(entries))
    sent = responses.calls[0].request
    import json as _json
    body = _json.loads(sent.body)
    assert body == {
        "activities": [
            {
                "date": "2026-06-01",
                "project_id": 123,
                "task_id": 456,
                "seconds": 28800,
                "description": "Administration",
                "billable": False,
            },
            {
                "date": "2026-06-02",
                "project_id": 123,
                "task_id": 456,
                "seconds": 16200,
                "description": "Administration",
                "billable": False,
            },
        ]
    }


@responses.activate
def test_bulk_create_opaque_2xx_marks_every_row_created(
    client: MocoClient,
) -> None:
    entries = [
        _planned_entry(_date(2026, 6, 1)),
        _planned_entry(_date(2026, 6, 2)),
    ]
    responses.add(
        responses.POST,
        f"{BASE_URL}/activities/bulk",
        json={"ok": True},  # not a per-row list
        status=200,
    )
    result = client.bulk_create(_batch(entries))
    assert result.created_count == 2
    assert result.failed_count == 0
    assert result.succeeded is True


@responses.activate
def test_bulk_create_per_row_response_with_errors_yields_mixed_results(
    client: MocoClient,
) -> None:
    """Speculative per-row response shape (FR-011) — verify the parsing."""
    entries = [
        _planned_entry(_date(2026, 6, 1)),
        _planned_entry(_date(2026, 6, 2)),
        _planned_entry(_date(2026, 6, 3)),
    ]
    responses.add(
        responses.POST,
        f"{BASE_URL}/activities/bulk",
        json=[
            {"id": 1},
            {"error": "Activity exists"},
            {"id": 2},
        ],
        status=200,
    )
    result = client.bulk_create(_batch(entries))
    assert result.created_count == 2
    assert result.failed_count == 1
    statuses = [e.status for e in result.entries]
    assert statuses == ["created", "failed", "created"]
    failed = [e for e in result.entries if e.status == "failed"][0]
    assert failed.date == _date(2026, 6, 2)
    assert failed.error_message == "Activity exists"


@responses.activate
def test_bulk_create_non_2xx_marks_every_row_failed(
    client: MocoClient,
) -> None:
    entries = [
        _planned_entry(_date(2026, 6, 1)),
        _planned_entry(_date(2026, 6, 2)),
    ]
    responses.add(
        responses.POST,
        f"{BASE_URL}/activities/bulk",
        body="something went wrong",
        status=500,
    )
    result = client.bulk_create(_batch(entries))
    assert result.created_count == 0
    assert result.failed_count == 2
    assert all(e.status == "failed" for e in result.entries)
    msg = result.entries[0].error_message or ""
    assert "500" in msg
    assert "something went wrong" in msg


@responses.activate
def test_bulk_create_raises_auth_error_on_401(client: MocoClient) -> None:
    entries = [_planned_entry(_date(2026, 6, 1))]
    responses.add(
        responses.POST,
        f"{BASE_URL}/activities/bulk",
        json={"error": "auth"},
        status=401,
    )
    with pytest.raises(AuthError):
        client.bulk_create(_batch(entries))


def test_bulk_create_returns_all_failed_on_transport_error(
    monkeypatch, client: MocoClient
) -> None:
    """Network-level exception (no HTTP response) — every row fails."""
    import requests as _requests

    def boom(*args, **kwargs):
        raise _requests.ConnectionError("connection refused")

    monkeypatch.setattr(client._session, "post", boom)
    entries = [
        _planned_entry(_date(2026, 6, 1)),
        _planned_entry(_date(2026, 6, 2)),
    ]
    result = client.bulk_create(_batch(entries))
    assert result.failed_count == 2
    assert all(
        "connection refused" in (e.error_message or "")
        for e in result.entries
    )
