"""Unit tests for moco_filler.planner — FR-005 + FR-012 + Q4 clarification."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from moco_filler.planner import build_planned_entries


def _activity(d: str, hours: float) -> dict:
    return {"date": d, "hours": hours}


# ---------- baseline: empty month ----------


def test_empty_month_defaults_every_weekday_to_8h() -> None:
    entries = build_planned_entries(2026, 6, [])
    # June 2026 has 22 weekdays.
    assert len(entries) == 22
    for e in entries:
        assert e.hours == Decimal("8")
        assert e.included is True
        assert e.already_logged is False
        assert e.existing_hours_total == Decimal("0")
        assert e.note is None


def test_empty_month_excludes_weekends() -> None:
    entries = build_planned_entries(2026, 6, [])
    weekdays = {e.date for e in entries}
    assert date(2026, 6, 6) not in weekdays  # Sat
    assert date(2026, 6, 7) not in weekdays  # Sun


# ---------- partial-day top-up (FR-012, Q4) ----------


def test_partial_day_auto_reduces_to_top_up_to_eight() -> None:
    entries = build_planned_entries(
        2026, 6, [_activity("2026-06-03", 4.5)]
    )
    by_date = {e.date: e for e in entries}
    partial = by_date[date(2026, 6, 3)]
    assert partial.existing_hours_total == Decimal("4.5")
    assert partial.hours == Decimal("3.5")
    assert partial.included is True
    assert partial.already_logged is False
    assert partial.note == "Top-up: existing 4.50h"


def test_partial_day_with_existing_below_one_hour() -> None:
    entries = build_planned_entries(
        2026, 6, [_activity("2026-06-03", 0.25)]
    )
    by_date = {e.date: e for e in entries}
    partial = by_date[date(2026, 6, 3)]
    assert partial.hours == Decimal("7.75")
    assert partial.included is True


def test_multiple_existing_entries_same_date_sum_across_projects() -> None:
    """Q4 clarification: sum hours per date across all projects/tasks."""
    entries = build_planned_entries(
        2026,
        6,
        [
            _activity("2026-06-03", 2.0),  # project A, task X
            _activity("2026-06-03", 1.5),  # project B, task Y
            _activity("2026-06-03", 1.0),  # project A, task Z
        ],
    )
    by_date = {e.date: e for e in entries}
    partial = by_date[date(2026, 6, 3)]
    assert partial.existing_hours_total == Decimal("4.5")
    assert partial.hours == Decimal("3.5")
    assert partial.included is True


# ---------- day-full lock (FR-012) ----------


def test_day_with_exactly_8h_existing_locks_as_already_logged() -> None:
    entries = build_planned_entries(
        2026, 6, [_activity("2026-06-03", 8.0)]
    )
    by_date = {e.date: e for e in entries}
    locked = by_date[date(2026, 6, 3)]
    assert locked.already_logged is True
    assert locked.included is False
    assert locked.hours == Decimal("0")
    assert "day full" in (locked.note or "")


def test_day_with_more_than_8h_existing_locks_as_already_logged() -> None:
    """Hypothetical: user logged 10h elsewhere → CLI must not push more."""
    entries = build_planned_entries(
        2026, 6, [_activity("2026-06-03", 10.0)]
    )
    by_date = {e.date: e for e in entries}
    locked = by_date[date(2026, 6, 3)]
    assert locked.already_logged is True
    assert locked.included is False


def test_summed_existing_at_exactly_8h_locks_day() -> None:
    entries = build_planned_entries(
        2026,
        6,
        [
            _activity("2026-06-03", 4.0),
            _activity("2026-06-03", 4.0),
        ],
    )
    by_date = {e.date: e for e in entries}
    locked = by_date[date(2026, 6, 3)]
    assert locked.already_logged is True


# ---------- robustness ----------


def test_activities_outside_month_are_ignored() -> None:
    entries = build_planned_entries(
        2026,
        6,
        [
            _activity("2026-05-29", 8.0),
            _activity("2026-07-01", 8.0),
        ],
    )
    # Every in-month weekday remains a default 8h plan.
    for e in entries:
        assert e.hours == Decimal("8")
        assert e.already_logged is False


def test_activities_on_weekends_are_ignored() -> None:
    """Saturday/Sunday activities never produce a PlannedEntry anyway."""
    entries = build_planned_entries(
        2026,
        6,
        [
            _activity("2026-06-06", 4.0),  # Saturday
            _activity("2026-06-07", 4.0),  # Sunday
        ],
    )
    # No weekend dates in the result, and no weekday inherits weekend hours.
    weekend_dates = {date(2026, 6, 6), date(2026, 6, 7)}
    assert all(e.date not in weekend_dates for e in entries)
    for e in entries:
        assert e.hours == Decimal("8")
        assert e.existing_hours_total == Decimal("0")


def test_malformed_activity_records_are_skipped() -> None:
    entries = build_planned_entries(
        2026,
        6,
        [
            {"date": None, "hours": 4.0},
            {"date": "not-a-date", "hours": 4.0},
            {"date": "2026-06-03"},  # missing hours
            {"date": "2026-06-04", "hours": "lots"},
            _activity("2026-06-05", 2.0),  # the only well-formed record
        ],
    )
    by_date = {e.date: e for e in entries}
    # 6/3 and 6/4 are unaffected by malformed records (hours treated as 0).
    assert by_date[date(2026, 6, 3)].hours == Decimal("8")
    assert by_date[date(2026, 6, 4)].hours == Decimal("8")
    # 6/5 gets the partial-day treatment.
    assert by_date[date(2026, 6, 5)].existing_hours_total == Decimal("2")
    assert by_date[date(2026, 6, 5)].hours == Decimal("6")


def test_returned_list_is_in_ascending_date_order() -> None:
    entries = build_planned_entries(2026, 6, [])
    dates = [e.date for e in entries]
    assert dates == sorted(dates)
