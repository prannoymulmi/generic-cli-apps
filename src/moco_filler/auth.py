"""Credential resolution for moco-filler.

Resolves the Moco API key in the priority order pinned by
``research.md`` §3:

1. ``MOCO_API_KEY`` environment variable, if set and non-empty.
2. Otherwise, an interactive masked prompt via ``questionary.password``.

The resolved token lives only in the returned ``ApiCredentials`` dataclass
and is passed to the HTTP client by reference. This module never writes
the token to a file, never logs it, and never accepts it via ``argv``
(per FR-001 and SC-004).
"""

from __future__ import annotations

import os

import questionary

from moco_filler.errors import CredentialMissingError
from moco_filler.models import ApiCredentials


ENV_VAR = "MOCO_API_KEY"
PROMPT_TEXT = "Moco API key:"


def resolve_credentials() -> ApiCredentials:
    """Return the API key for this run, never touching the filesystem."""
    env_token = os.environ.get(ENV_VAR, "").strip()
    if env_token:
        return ApiCredentials(token=env_token, source="env")

    raw = questionary.password(PROMPT_TEXT).ask()
    token = (raw or "").strip()
    if not token:
        raise CredentialMissingError(
            "No API key provided. Set MOCO_API_KEY or supply a key "
            "when prompted."
        )
    return ApiCredentials(token=token, source="prompt")
