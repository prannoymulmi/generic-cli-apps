"""Unit tests for moco_filler.models — data-model.md invariants."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

import pytest

from moco_filler.models import (
    ApiCredentials,
    EntryResult,
    PlannedEntry,
    Project,
    SubmissionBatch,
    SubmissionResult,
    Task,
)


WEEKDAY = date(2026, 6, 3)
SATURDAY = date(2026, 6, 6)
SUNDAY = date(2026, 6, 7)


def _entry(
    *,
    d: date = WEEKDAY,
    existing: str = "0",
    hours: str = "8",
    included: bool = True,
    already_logged: bool = False,
    note: Optional[str] = None,
) -> PlannedEntry:
    return PlannedEntry(
        date=d,
        weekday=d.strftime("%a"),
        existing_hours_total=Decimal(existing),
        hours=Decimal(hours),
        included=included,
        already_logged=already_logged,
        note=note,
    )


# ---------- ApiCredentials ----------


def test_api_credentials_accepts_env_source() -> None:
    creds = ApiCredentials(token="abc", source="env")
    assert creds.source == "env"


def test_api_credentials_accepts_prompt_source() -> None:
    creds = ApiCredentials(token="abc", source="prompt")
    assert creds.source == "prompt"


@pytest.mark.parametrize("bad_token", ["", "   ", "\t\n"])
def test_api_credentials_rejects_empty_token(bad_token: str) -> None:
    with pytest.raises(ValueError):
        ApiCredentials(token=bad_token, source="env")


# ---------- PlannedEntry ----------


@pytest.mark.parametrize("weekend_date", [SATURDAY, SUNDAY])
def test_planned_entry_rejects_weekend_date(weekend_date: date) -> None:
    with pytest.raises(ValueError):
        _entry(d=weekend_date)


@pytest.mark.parametrize("bad_hours", ["-0.1", "8.01", "16", "-1"])
def test_planned_entry_rejects_out_of_range_hours(bad_hours: str) -> None:
    with pytest.raises(ValueError):
        _entry(hours=bad_hours)


def test_planned_entry_rejects_negative_existing_total() -> None:
    with pytest.raises(ValueError):
        _entry(existing="-0.5")


def test_planned_entry_rejects_already_logged_with_included_true() -> None:
    with pytest.raises(ValueError):
        _entry(already_logged=True, included=True, hours="0")


def test_planned_entry_already_logged_with_included_false_is_valid() -> None:
    entry = _entry(already_logged=True, included=False, hours="0")
    assert entry.already_logged is True
    assert entry.included is False


def test_is_submitable_true_when_default_planned_row() -> None:
    assert _entry().is_submitable is True


def test_is_submitable_false_when_skipped() -> None:
    assert _entry(included=False, hours="0").is_submitable is False


def test_is_submitable_false_when_zero_hours() -> None:
    assert _entry(hours="0", included=True).is_submitable is False


def test_is_submitable_false_when_already_logged() -> None:
    entry = _entry(already_logged=True, included=False, hours="0")
    assert entry.is_submitable is False


def test_seconds_for_full_day() -> None:
    assert _entry(hours="8").seconds == 28800


def test_seconds_for_partial_day() -> None:
    assert _entry(hours="4.5").seconds == 16200


def test_seconds_for_zero_hours() -> None:
    assert _entry(hours="0").seconds == 0


# ---------- SubmissionBatch ----------


def _make_batch(entries: list) -> SubmissionBatch:
    return SubmissionBatch(
        project_id=1,
        task_id=2,
        description="Administration",
        billable=False,
        entries=entries,
    )


def test_submission_batch_rejects_empty_entries() -> None:
    with pytest.raises(ValueError):
        _make_batch([])


def test_submission_batch_rejects_duplicate_dates() -> None:
    e = _entry()
    with pytest.raises(ValueError):
        _make_batch([e, e])


def test_submission_batch_rejects_non_submitable_entries() -> None:
    skipped = _entry(included=False, hours="0")
    with pytest.raises(ValueError):
        _make_batch([skipped])


def test_submission_batch_accepts_valid_entries() -> None:
    e1 = _entry(d=date(2026, 6, 1))
    e2 = _entry(d=date(2026, 6, 2))
    batch = _make_batch([e1, e2])
    assert len(batch.entries) == 2


# ---------- EntryResult ----------


def test_entry_result_created_with_no_message_is_valid() -> None:
    r = EntryResult(date=WEEKDAY, status="created")
    assert r.error_message is None


def test_entry_result_created_must_not_carry_error_message() -> None:
    with pytest.raises(ValueError):
        EntryResult(date=WEEKDAY, status="created", error_message="boom")


def test_entry_result_failed_with_message() -> None:
    r = EntryResult(date=WEEKDAY, status="failed", error_message="500")
    assert r.error_message == "500"


def test_entry_result_failed_without_message_is_allowed() -> None:
    # data-model.md permits None when Moco does not surface a per-row reason.
    r = EntryResult(date=WEEKDAY, status="failed", error_message=None)
    assert r.status == "failed"


# ---------- SubmissionResult ----------


def test_submission_result_all_created() -> None:
    result = SubmissionResult(
        entries=[
            EntryResult(date=date(2026, 6, 1), status="created"),
            EntryResult(date=date(2026, 6, 2), status="created"),
        ]
    )
    assert result.created_count == 2
    assert result.failed_count == 0
    assert result.succeeded is True
    assert result.any_created is True


def test_submission_result_all_failed() -> None:
    result = SubmissionResult(
        entries=[
            EntryResult(
                date=date(2026, 6, 1),
                status="failed",
                error_message="upstream",
            ),
            EntryResult(
                date=date(2026, 6, 2),
                status="failed",
                error_message="upstream",
            ),
        ]
    )
    assert result.created_count == 0
    assert result.failed_count == 2
    assert result.succeeded is False
    assert result.any_created is False


def test_submission_result_mixed() -> None:
    result = SubmissionResult(
        entries=[
            EntryResult(date=date(2026, 6, 1), status="created"),
            EntryResult(
                date=date(2026, 6, 2),
                status="failed",
                error_message="500",
            ),
            EntryResult(date=date(2026, 6, 3), status="created"),
        ]
    )
    assert result.created_count == 2
    assert result.failed_count == 1
    assert result.succeeded is False
    assert result.any_created is True


def test_submission_result_empty_is_vacuously_succeeded() -> None:
    # The data-model.md formula for `succeeded` is
    # `failed_count == 0 and created_count == len(entries)`, which is
    # vacuously True for the empty case. SubmissionResult is only ever
    # built from a non-empty SubmissionBatch in practice (the empty
    # case is gated upstream by NothingToSubmitError → exit 5), so this
    # corner is documented behaviour rather than load-bearing.
    result = SubmissionResult(entries=[])
    assert result.created_count == 0
    assert result.failed_count == 0
    assert result.succeeded is True
    assert result.any_created is False


# ---------- Project / Task (smoke) ----------


def test_project_can_hold_tasks() -> None:
    project = Project(
        id=1,
        name="Internal",
        tasks=[Task(id=10, name="Administration")],
    )
    assert project.tasks[0].name == "Administration"


def test_project_defaults_to_empty_task_list() -> None:
    project = Project(id=2, name="Empty")
    assert project.tasks == []
