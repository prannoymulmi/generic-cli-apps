"""Unit tests for moco_filler.auth — resolution, persistence, recovery."""

from __future__ import annotations

from typing import Any, Optional

import pytest

from moco_filler import credential_store
from moco_filler.auth import (
    ENV_VAR,
    authenticate,
    persist_if_new,
    resolve_credentials,
)
from moco_filler.errors import AuthError, CredentialMissingError
from moco_filler.models import ApiCredentials


class _FakeQuestion:
    """Stand-in for the object ``questionary.password`` returns."""

    def __init__(self, answer: Optional[str]) -> None:
        self._answer = answer

    def ask(self) -> Optional[str]:
        return self._answer


@pytest.fixture(autouse=True)
def fake_store(monkeypatch):
    """In-memory stand-in for the on-disk store; no real home dir touched.

    Autouse so every test is isolated from a developer's real cached key.
    Returns the backing state dict so tests can seed / assert the store.
    """
    state: dict = {"token": None, "writes": 0, "raise_on_write": False}

    def _read():
        return state["token"]

    def _write(token: str):
        if state["raise_on_write"]:
            raise OSError("simulated read-only filesystem")
        state["token"] = token
        state["writes"] += 1

    def _delete():
        state["token"] = None

    monkeypatch.setattr(credential_store, "read_stored_token", _read)
    monkeypatch.setattr(credential_store, "write_token", _write)
    monkeypatch.setattr(credential_store, "delete_token", _delete)
    return state


@pytest.fixture
def no_env(monkeypatch) -> None:
    monkeypatch.delenv(ENV_VAR, raising=False)


@pytest.fixture
def with_env(monkeypatch):
    def _set(value: str) -> None:
        monkeypatch.setenv(ENV_VAR, value)
    return _set


@pytest.fixture
def fake_prompt(monkeypatch):
    """Replace ``questionary.password`` so we never actually prompt."""
    calls: list = []

    def _install(answer: Optional[str]) -> None:
        def _password(prompt_text: str) -> _FakeQuestion:
            calls.append(prompt_text)
            return _FakeQuestion(answer)
        monkeypatch.setattr("moco_filler.auth.questionary.password", _password)

    _install.calls = calls  # type: ignore[attr-defined]
    return _install


# ---------- env path ----------


def test_env_var_present_returns_env_source(
    no_env, with_env, fake_prompt
) -> None:
    fake_prompt(None)
    with_env("env-token")
    creds = resolve_credentials()
    assert creds.token == "env-token"
    assert creds.source == "env"
    assert fake_prompt.calls == []  # type: ignore[attr-defined]


def test_env_var_with_whitespace_is_trimmed(
    no_env, with_env, fake_prompt
) -> None:
    fake_prompt(None)
    with_env("  whitespace-token  ")
    creds = resolve_credentials()
    assert creds.token == "whitespace-token"
    assert creds.source == "env"


def test_empty_env_falls_through_to_prompt(
    no_env, with_env, fake_prompt
) -> None:
    fake_prompt("prompt-token")
    with_env("   ")  # whitespace-only
    creds = resolve_credentials()
    assert creds.source == "prompt"
    assert creds.token == "prompt-token"
    assert len(fake_prompt.calls) == 1  # type: ignore[attr-defined]


# ---------- prompt path ----------


def test_prompt_when_env_unset(no_env, fake_prompt) -> None:
    fake_prompt("typed-token")
    creds = resolve_credentials()
    assert creds.token == "typed-token"
    assert creds.source == "prompt"


def test_prompt_with_whitespace_is_trimmed(no_env, fake_prompt) -> None:
    fake_prompt("  spaced-token  ")
    creds = resolve_credentials()
    assert creds.token == "spaced-token"


@pytest.mark.parametrize("empty", [None, "", "   ", "\t"])
def test_empty_prompt_answer_raises_credential_missing(
    no_env, fake_prompt, empty
) -> None:
    fake_prompt(empty)
    with pytest.raises(CredentialMissingError):
        resolve_credentials()


# ---------- SC-004: token must not leak to stdout/stderr ----------


def test_resolution_does_not_echo_token(
    no_env, with_env, fake_prompt, capsys
) -> None:
    fake_prompt(None)
    with_env("super-secret-deadbeef-12345")
    resolve_credentials()
    captured = capsys.readouterr()
    assert "super-secret-deadbeef-12345" not in captured.out
    assert "super-secret-deadbeef-12345" not in captured.err


def test_prompt_path_does_not_echo_token(
    no_env, fake_prompt, capsys
) -> None:
    fake_prompt("prompt-secret-deadbeef-67890")
    resolve_credentials()
    captured = capsys.readouterr()
    assert "prompt-secret-deadbeef-67890" not in captured.out
    assert "prompt-secret-deadbeef-67890" not in captured.err


# ---------- US1: store precedence + reuse (AR-1, AR-7) ----------


def test_stored_key_used_without_prompt(
    no_env, fake_prompt, fake_store
) -> None:
    fake_prompt(None)
    fake_store["token"] = "stored-token"
    creds = resolve_credentials()
    assert creds.token == "stored-token"
    assert creds.source == "store"
    assert fake_prompt.calls == []  # type: ignore[attr-defined]


def test_env_takes_precedence_over_stored_key(
    no_env, with_env, fake_prompt, fake_store
) -> None:
    fake_prompt(None)
    fake_store["token"] = "stored-token"
    with_env("env-token")
    creds = resolve_credentials()
    assert creds.token == "env-token"
    assert creds.source == "env"


def test_prompt_only_when_env_and_store_empty(
    no_env, fake_prompt, fake_store
) -> None:
    fake_prompt("typed-token")
    fake_store["token"] = None
    creds = resolve_credentials()
    assert creds.source == "prompt"
    assert len(fake_prompt.calls) == 1  # type: ignore[attr-defined]


# ---------- US1: authenticate happy path + persistence (AR-1, AR-2) -----


def _ok(_token: str) -> str:
    """A validator that always succeeds, returning a sentinel result."""
    return "session-result"


def test_authenticate_persists_validated_prompt_key(
    no_env, fake_prompt, fake_store
) -> None:
    fake_prompt("new-key")
    creds, result = authenticate(_ok)
    assert creds.source == "prompt"
    assert result == "session-result"
    assert fake_store["token"] == "new-key"
    assert fake_store["writes"] == 1


def test_authenticate_stored_key_skips_prompt_and_does_not_rewrite(
    no_env, fake_prompt, fake_store
) -> None:
    fake_prompt(None)
    fake_store["token"] = "good-stored"
    creds, _ = authenticate(_ok)
    assert creds.source == "store"
    assert fake_prompt.calls == []  # type: ignore[attr-defined]
    # No redundant write when the resolved key already equals the store.
    assert fake_store["writes"] == 0


def test_persist_if_new_skips_write_when_unchanged(fake_store) -> None:
    fake_store["token"] = "same"
    persist_if_new(ApiCredentials(token="same", source="store"))
    assert fake_store["writes"] == 0


# ---------- US3: rejected-stored-key recovery (AR-4, AR-5, AR-6) --------


def test_rejected_stored_key_is_forgotten_then_reprompted(
    no_env, fake_prompt, fake_store, capsys
) -> None:
    fake_store["token"] = "revoked-key"
    fake_prompt("fresh-key")

    def _reject_only_revoked(token: str) -> str:
        if token == "revoked-key":
            raise AuthError("rejected")
        return "ok"

    creds, result = authenticate(_reject_only_revoked)
    assert creds.token == "fresh-key"
    assert creds.source == "prompt"
    assert result == "ok"
    # The new key replaces the revoked one.
    assert fake_store["token"] == "fresh-key"
    # The user was told why they were re-prompted (on stderr, no token).
    err = capsys.readouterr().err
    assert "rejected" in err.lower()
    assert "revoked-key" not in err


def test_second_rejection_propagates_without_loop(
    no_env, fake_prompt, fake_store
) -> None:
    fake_store["token"] = "revoked-key"
    fake_prompt("also-bad")

    def _always_reject(_token: str) -> str:
        raise AuthError("nope")

    with pytest.raises(AuthError):
        authenticate(_always_reject)


def test_malformed_store_falls_through_to_prompt(
    no_env, fake_prompt, fake_store
) -> None:
    # A malformed store reads as None (see test_credential_store); model
    # that here as an empty store and confirm the prompt path runs.
    fake_store["token"] = None
    fake_prompt("typed-after-bad-store")
    creds, _ = authenticate(_ok)
    assert creds.source == "prompt"
    assert fake_store["token"] == "typed-after-bad-store"


# ---------- US4: override + replace/remove (AR-3, AR-7, AR-8) -----------


def test_env_key_is_persisted_replacing_prior_store(
    no_env, with_env, fake_prompt, fake_store
) -> None:
    fake_prompt(None)
    fake_store["token"] = "old-stored"
    with_env("env-supplied")
    creds, _ = authenticate(_ok)
    assert creds.source == "env"
    assert fake_store["token"] == "env-supplied"


def test_deleting_store_returns_to_prompt(
    no_env, fake_prompt, fake_store
) -> None:
    fake_store["token"] = "to-be-deleted"
    credential_store.delete_token()
    fake_prompt("typed-again")
    creds = resolve_credentials()
    assert creds.source == "prompt"


def test_save_failure_warns_and_run_continues(
    no_env, fake_prompt, fake_store, capsys
) -> None:
    fake_prompt("unsavable-key")
    fake_store["raise_on_write"] = True
    creds, result = authenticate(_ok)
    # The run still completes with the in-memory token.
    assert creds.token == "unsavable-key"
    assert result == "session-result"
    err = capsys.readouterr().err
    assert "could not save" in err.lower()
    assert "unsavable-key" not in err
