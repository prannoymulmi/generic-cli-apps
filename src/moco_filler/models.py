"""In-memory data shapes for moco-filler.

Mirrors ``specs/001-create-mvp-moco-filler-app/data-model.md``. Nothing here is
persisted: the API key and every session entity live only for the
duration of one run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date
from decimal import Decimal
from typing import List, Literal, Optional


HOURS_FLOOR = Decimal("0")
HOURS_CAP = Decimal("8")
DAY_FULL_THRESHOLD = Decimal("8")
SECONDS_PER_HOUR = 3600


@dataclass
class ApiCredentials:
    """The API key resolved for this run, plus where it came from.

    ``source`` exists so diagnostics can say where the token was supplied
    from without ever printing the token itself. Feature 005 adds
    ``"store"`` for a key read from the on-disk credential cache; the
    value still never appears in any log line.
    """

    token: str
    source: Literal["env", "store", "prompt"]

    def __post_init__(self) -> None:
        if not self.token or not self.token.strip():
            raise ValueError("ApiCredentials.token must be a non-empty string")


@dataclass
class Task:
    """A task (service) inside a Moco project."""

    id: int
    name: str


@dataclass
class Project:
    """A Moco project the user can book against."""

    id: int
    name: str
    tasks: List[Task] = field(default_factory=list)


@dataclass
class PlannedEntry:
    """One row of the preview table.

    See data-model.md for the partial-day top-up rule (FR-012), the
    ``[0, 8]`` hours range invariant (FR-008), and the already-logged
    lock (FR-012). Construction-time invariants live in
    ``__post_init__`` so callers can't sneak inconsistent state past
    the dataclass.
    """

    date: _date
    weekday: str
    existing_hours_total: Decimal
    hours: Decimal
    included: bool
    already_logged: bool
    note: Optional[str] = None
    holiday_name: Optional[str] = None

    def __post_init__(self) -> None:
        if self.date.weekday() >= 5:
            raise ValueError(
                f"PlannedEntry.date must be Mon-Fri; got {self.date} "
                f"({self.weekday})"
            )

        if self.existing_hours_total < HOURS_FLOOR:
            raise ValueError(
                "PlannedEntry.existing_hours_total must be >= 0; got "
                f"{self.existing_hours_total}"
            )

        if not (HOURS_FLOOR <= self.hours <= HOURS_CAP):
            raise ValueError(
                f"PlannedEntry.hours must be within [{HOURS_FLOOR}, "
                f"{HOURS_CAP}]; got {self.hours}"
            )

        if self.already_logged and self.included:
            # FR-012: locked rows are excluded from the submission and the
            # UI cannot toggle them back to included.
            raise ValueError(
                "PlannedEntry with already_logged=True must have "
                "included=False"
            )

    @property
    def is_submitable(self) -> bool:
        """True iff this row should appear in the bulk submission."""
        return (
            self.included
            and self.hours > HOURS_FLOOR
            and not self.already_logged
        )

    @property
    def seconds(self) -> int:
        """``seconds`` value for the Moco bulk endpoint (moco-http.md)."""
        return int(self.hours * SECONDS_PER_HOUR)


@dataclass
class SubmissionBatch:
    """The payload that goes to ``POST /activities/bulk``.

    Construct only from submitable ``PlannedEntry`` rows. Empty batches
    are a hard error (the CLI exits with code ``5`` via
    ``NothingToSubmitError`` before getting here).
    """

    project_id: int
    task_id: int
    description: str
    billable: bool
    entries: List[PlannedEntry]

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValueError("SubmissionBatch.entries must be non-empty")

        dates = [e.date for e in self.entries]
        if len(set(dates)) != len(dates):
            raise ValueError(
                "SubmissionBatch must not contain duplicate dates"
            )

        for entry in self.entries:
            if not entry.is_submitable:
                raise ValueError(
                    f"SubmissionBatch entry for {entry.date} is not "
                    "submitable"
                )


@dataclass
class EntryResult:
    """Per-row outcome of ``POST /activities/bulk`` (FR-011)."""

    date: _date
    status: Literal["created", "failed"]
    error_message: Optional[str] = None

    def __post_init__(self) -> None:
        # data-model.md allows a failed row to have error_message=None
        # when Moco's bulk endpoint returns opaquely; only the
        # "created with an error message" combination is forbidden.
        if self.status == "created" and self.error_message is not None:
            raise ValueError(
                "EntryResult(status='created') must not carry an "
                "error_message"
            )


@dataclass
class SubmissionResult:
    """The aggregate per-row outcome of one bulk submission."""

    entries: List[EntryResult]

    @property
    def created_count(self) -> int:
        return sum(1 for e in self.entries if e.status == "created")

    @property
    def failed_count(self) -> int:
        return sum(1 for e in self.entries if e.status == "failed")

    @property
    def succeeded(self) -> bool:
        return (
            self.failed_count == 0
            and self.created_count == len(self.entries)
        )

    @property
    def any_created(self) -> bool:
        return self.created_count > 0
