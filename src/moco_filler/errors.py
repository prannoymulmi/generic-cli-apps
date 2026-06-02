"""Domain exceptions for moco-filler.

Each exception class carries the exit code that the top-level CLI returns
when it propagates. Centralising the mapping here keeps the CLI glue thin
and makes per-error behaviour explicitly testable.

Exit codes follow ``specs/001-create-mvp-moco-filler-app/contracts/cli.md`` §
"Exit codes" and ``research.md`` §6.
"""

from __future__ import annotations


class MocoFillerError(Exception):
    """Base class for all moco-filler domain errors.

    Subclasses set a stable ``exit_code`` so the CLI can map an
    exception type to its contracted process exit status without
    inspecting messages.
    """

    exit_code: int = 1


class CredentialMissingError(MocoFillerError):
    """No API key could be resolved from env var or prompt.

    Maps to the same exit code as ``AuthError`` because, from the user's
    perspective, both mean "we could not authenticate this run".
    """

    exit_code = 2


class AuthError(MocoFillerError):
    """Moco rejected the API key (HTTP 401 / 403)."""

    exit_code = 2


class NoProjectsError(MocoFillerError):
    """``GET /projects/assigned`` returned no projects."""

    exit_code = 3


class NoTasksError(MocoFillerError):
    """The chosen project has no tasks."""

    exit_code = 4


class NothingToSubmitError(MocoFillerError):
    """Every planned row was skipped or already logged."""

    exit_code = 5


class BulkTotalFailureError(MocoFillerError):
    """``POST /activities/bulk`` created zero rows."""

    exit_code = 6


class BulkPartialFailureError(MocoFillerError):
    """``POST /activities/bulk`` created some rows and failed others."""

    exit_code = 7
