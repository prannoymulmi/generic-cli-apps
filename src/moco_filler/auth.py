"""Credential resolution and persistence for moco-filler.

Resolves the Moco API key for a run in the precedence order pinned by
``specs/005-cache-moco-api-key/contracts/auth-resolution.md``:

1. ``MOCO_API_KEY`` environment variable, if set and non-empty.
2. Otherwise, the locally cached key from ``credential_store``.
3. Otherwise, an interactive masked prompt via ``questionary.password``.

A key that successfully authenticates is written back to the local store
(feature 005) so the user is prompted at most once. The token value is
never written to ``argv``, never logged, and the prompt stays masked
(FR-014); only ``ApiCredentials.source`` is used for diagnostics.
"""

from __future__ import annotations

import os
import sys
from typing import Callable, Tuple, TypeVar

import questionary

from moco_filler import credential_store
from moco_filler.errors import AuthError, CredentialMissingError
from moco_filler.models import ApiCredentials


ENV_VAR = "MOCO_API_KEY"
PROMPT_TEXT = "Moco API key:"

T = TypeVar("T")


def resolve_credentials() -> ApiCredentials:
    """Return the API key for this run in env → store → prompt order."""
    env_token = os.environ.get(ENV_VAR, "").strip()
    if env_token:
        return ApiCredentials(token=env_token, source="env")

    stored_token = credential_store.read_stored_token()
    if stored_token:
        return ApiCredentials(token=stored_token, source="store")

    return prompt_for_credentials()


def prompt_for_credentials() -> ApiCredentials:
    """Force the masked prompt, bypassing env var and store.

    Used for first-run entry and for the reject-recovery path. An empty
    entry raises :class:`CredentialMissingError`.
    """
    raw = questionary.password(PROMPT_TEXT).ask()
    token = (raw or "").strip()
    if not token:
        raise CredentialMissingError(
            "No API key provided. Set MOCO_API_KEY or supply a key "
            "when prompted."
        )
    return ApiCredentials(token=token, source="prompt")


def persist_if_new(creds: ApiCredentials) -> None:
    """Write the token to the local store iff it differs from what's saved.

    Persists a validated key regardless of source — including one
    supplied via ``MOCO_API_KEY`` (FR-005, FR-015). Skips the write when
    the key already came from the store unchanged. A filesystem failure
    is not fatal: the run continues with a single stderr warning (FR-013).
    """
    if creds.token == credential_store.read_stored_token():
        return
    try:
        credential_store.write_token(creds.token)
    except OSError:
        print(
            "Warning: could not save the Moco API key; you may be "
            "prompted again next time.",
            file=sys.stderr,
        )


def forget_stored_credential() -> None:
    """Delete the locally cached key (reject-recovery, FR-006)."""
    credential_store.delete_token()


def authenticate(validate: Callable[[str], T]) -> Tuple[ApiCredentials, T]:
    """Resolve, validate, recover from a rejected stored key, and persist.

    ``validate(token)`` MUST raise :class:`AuthError` when Moco rejects
    the key and return any value otherwise; keeping it injectable lets
    this module stay transport-agnostic and unit-testable.

    Flow: resolve the key, validate it. If a *stored* key is rejected,
    discard it, warn, and re-prompt once; a second rejection propagates
    (exit code 2, no infinite loop). On success, persist the key when it
    differs from the stored value and return ``(credentials, result)``.
    """
    creds = resolve_credentials()
    try:
        result = validate(creds.token)
    except AuthError:
        if creds.source == "store":
            forget_stored_credential()
            print(
                "Saved Moco API key was rejected; please re-enter.",
                file=sys.stderr,
            )
        creds = prompt_for_credentials()
        result = validate(creds.token)

    persist_if_new(creds)
    return creds, result
