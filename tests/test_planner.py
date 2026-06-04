"""Unit tests for moco_filler.planner — FR-005 + FR-012 + Q4 clarification."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from moco_filler.models import PlannedEntry
from moco_filler.planner import (
    build_planned_entries,
    set_hours,
    toggle_skipped,
)


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


# ---------- US3 row edit helpers ----------


def _plain_row(d: date = date(2026, 6, 3)) -> PlannedEntry:
    return PlannedEntry(
        date=d,
        weekday=d.strftime("%a"),
        existing_hours_total=Decimal("0"),
        hours=Decimal("8"),
        included=True,
        already_logged=False,
        note=None,
    )


def _top_up_row(d: date = date(2026, 6, 4)) -> PlannedEntry:
    return PlannedEntry(
        date=d,
        weekday=d.strftime("%a"),
        existing_hours_total=Decimal("4.5"),
        hours=Decimal("3.5"),
        included=True,
        already_logged=False,
        note="Top-up: existing 4.50h",
    )


def _locked_row(d: date = date(2026, 6, 5)) -> PlannedEntry:
    return PlannedEntry(
        date=d,
        weekday=d.strftime("%a"),
        existing_hours_total=Decimal("8"),
        hours=Decimal("0"),
        included=False,
        already_logged=True,
        note="Already logged (8.00h, day full)",
    )


def test_set_hours_to_valid_value_keeps_row_included() -> None:
    row = _plain_row()
    edited = set_hours(row, Decimal("4"))
    assert edited.hours == Decimal("4")
    assert edited.included is True
    # The original row is unchanged (set_hours returns a new instance).
    assert row.hours == Decimal("8")


def test_set_hours_to_zero_auto_skips_row() -> None:
    """Q2 clarification (2026-06-01): hours=0 ⇒ included=False."""
    edited = set_hours(_plain_row(), Decimal("0"))
    assert edited.hours == Decimal("0")
    assert edited.included is False


def test_set_hours_to_eight_is_allowed_upper_bound() -> None:
    edited = set_hours(_top_up_row(), Decimal("8"))
    assert edited.hours == Decimal("8")
    assert edited.included is True


def test_set_hours_negative_raises() -> None:
    with pytest.raises(ValueError):
        set_hours(_plain_row(), Decimal("-1"))


def test_set_hours_above_eight_raises() -> None:
    """Q3 clarification (2026-06-01): hours capped at 8."""
    with pytest.raises(ValueError):
        set_hours(_plain_row(), Decimal("8.01"))


def test_set_hours_on_already_logged_row_is_refused() -> None:
    """FR-012: locked rows reject edits."""
    with pytest.raises(ValueError):
        set_hours(_locked_row(), Decimal("4"))


def test_toggle_skipped_includes_to_skipped_and_back() -> None:
    row = _plain_row()
    skipped = toggle_skipped(row)
    assert skipped.included is False
    assert skipped.hours == row.hours  # hours preserved across skip
    re_included = toggle_skipped(skipped)
    assert re_included.included is True
    assert re_included.hours == row.hours


def test_toggle_skipped_on_top_up_row() -> None:
    row = _top_up_row()
    skipped = toggle_skipped(row)
    assert skipped.included is False
    assert skipped.existing_hours_total == row.existing_hours_total


def test_toggle_skipped_on_already_logged_row_is_refused() -> None:
    """FR-012: locked rows cannot be toggled back to included."""
    with pytest.raises(ValueError):
        toggle_skipped(_locked_row())


# ---- feature 003 / 004: Hamburg holiday catalogue (US1) -----------------


def test_holiday_weekday_is_auto_skipped() -> None:
    """US1 AC-1: a Hamburg holiday weekday is built as not-included."""
    entries = build_planned_entries(
        2026,
        5,
        [],
        holiday_catalogue={date(2026, 5, 1): "Tag der Arbeit"},
    )
    by_date = {e.date: e for e in entries}
    holiday = by_date[date(2026, 5, 1)]
    assert holiday.holiday_name == "Tag der Arbeit"
    assert holiday.included is False
    assert holiday.hours == Decimal("0")
    assert holiday.already_logged is False
    assert holiday.is_submitable is False


def test_other_weekdays_unchanged_when_holiday_catalogue_set() -> None:
    """Only the catalogue dates are affected; everything else is normal."""
    entries = build_planned_entries(
        2026,
        5,
        [],
        holiday_catalogue={date(2026, 5, 1): "Tag der Arbeit"},
    )
    non_holiday = [e for e in entries if e.date != date(2026, 5, 1)]
    for e in non_holiday:
        assert e.hours == Decimal("8")
        assert e.included is True
        assert e.holiday_name is None


def test_holiday_plus_already_logged_yields_locked_with_holiday_metadata() -> None:
    """FR-005: already-logged wins, but holiday_name is preserved."""
    entries = build_planned_entries(
        2026,
        4,
        [_activity("2026-04-03", 8.0)],  # Karfreitag, fully logged
        holiday_catalogue={date(2026, 4, 3): "Karfreitag"},
    )
    by_date = {e.date: e for e in entries}
    row = by_date[date(2026, 4, 3)]
    assert row.already_logged is True
    assert row.included is False
    assert row.holiday_name == "Karfreitag"


def test_empty_holiday_catalogue_is_graceful_fallback() -> None:
    """FR-007 / FR-013: an empty catalogue means no holidays marked."""
    entries = build_planned_entries(2026, 6, [], holiday_catalogue={})
    for e in entries:
        assert e.holiday_name is None
        assert e.hours == Decimal("8")
        assert e.included is True


def test_no_holiday_catalogue_argument_matches_old_behaviour() -> None:
    """Existing call sites without the new argument keep working."""
    entries = build_planned_entries(2026, 6, [])
    for e in entries:
        assert e.holiday_name is None


# ---- feature 003 / 004: US3 override loop -------------------------------


def _holiday_auto_skipped(d: date = date(2026, 5, 1)) -> PlannedEntry:
    """A row in the canonical 'holiday auto-skipped' shape."""
    return PlannedEntry(
        date=d,
        weekday=d.strftime("%a"),
        existing_hours_total=Decimal("0"),
        hours=Decimal("0"),
        included=False,
        already_logged=False,
        note="Holiday: Tag der Arbeit",
        holiday_name="Tag der Arbeit",
    )


def test_toggle_skipped_includes_holiday_row_with_default_hours() -> None:
    """US3 AC-1: re-including a holiday row produces a submitable row."""
    row = _holiday_auto_skipped()
    overridden = toggle_skipped(row)
    assert overridden.included is True
    assert overridden.hours == Decimal("8")
    assert overridden.holiday_name == "Tag der Arbeit"  # metadata kept
    assert overridden.is_submitable is True


def test_toggle_skipped_includes_holiday_row_with_existing_hours_tops_up() -> None:
    """Re-including a holiday day that has partial pre-existing hours tops up."""
    row = PlannedEntry(
        date=date(2026, 5, 1),
        weekday="Fri",
        existing_hours_total=Decimal("3"),
        hours=Decimal("0"),
        included=False,
        already_logged=False,
        note="Holiday: Tag der Arbeit",
        holiday_name="Tag der Arbeit",
    )
    overridden = toggle_skipped(row)
    assert overridden.included is True
    assert overridden.hours == Decimal("5")  # 8 - 3 existing
    assert overridden.holiday_name == "Tag der Arbeit"


def test_toggle_skipped_re_skips_overridden_holiday_to_canonical_shape() -> None:
    """FR-007: re-skipping a re-included holiday returns to hours=0."""
    overridden = PlannedEntry(
        date=date(2026, 5, 1),
        weekday="Fri",
        existing_hours_total=Decimal("0"),
        hours=Decimal("8"),
        included=True,
        already_logged=False,
        note="Holiday: Tag der Arbeit",
        holiday_name="Tag der Arbeit",
    )
    re_skipped = toggle_skipped(overridden)
    assert re_skipped.included is False
    assert re_skipped.hours == Decimal("0")
    assert re_skipped.holiday_name == "Tag der Arbeit"


def test_toggle_skipped_on_already_logged_holiday_still_refused() -> None:
    """The FR-012 lock applies to any already-logged row, holiday or not."""
    row = PlannedEntry(
        date=date(2026, 4, 3),
        weekday="Fri",
        existing_hours_total=Decimal("8"),
        hours=Decimal("0"),
        included=False,
        already_logged=True,
        note="Already logged (8.00h, day full)",
        holiday_name="Karfreitag",
    )
    with pytest.raises(ValueError):
        toggle_skipped(row)


def test_toggle_skipped_non_holiday_row_still_preserves_hours() -> None:
    """Regression: non-holiday rows keep the original toggle behaviour."""
    row = _plain_row()
    skipped = toggle_skipped(row)
    # The pre-existing behaviour: hours preserved across skip on non-holiday rows.
    assert skipped.included is False
    assert skipped.hours == row.hours
