"""Unit tests for moco_filler.auth — FR-001 + SC-004 safety properties."""

from __future__ import annotations

from typing import Any, Optional

import pytest

from moco_filler.auth import ENV_VAR, resolve_credentials
from moco_filler.errors import CredentialMissingError


class _FakeQuestion:
    """Stand-in for the object ``questionary.password`` returns."""

    def __init__(self, answer: Optional[str]) -> None:
        self._answer = answer

    def ask(self) -> Optional[str]:
        return self._answer


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
