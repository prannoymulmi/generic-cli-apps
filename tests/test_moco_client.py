"""Unit tests for moco_filler.moco_client — see contracts/moco-http.md.

Each Moco endpoint is mocked via the ``responses`` library. We assert
both the *shape* of the request we send (URL, headers, query params,
body) and how we map the response back to domain dataclasses, plus the
error → exception mapping.
"""

from __future__ import annotations

import pytest
import responses

from moco_filler.errors import AuthError
from moco_filler.moco_client import MocoClient


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
