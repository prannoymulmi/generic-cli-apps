"""Unit tests for moco_filler.calendar_utils."""

from __future__ import annotations

from datetime import date

import pytest

from moco_filler.calendar_utils import parse_month, weekday_dates


# ---------- parse_month ----------


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2026-06", (2026, 6)),
        ("2026-01", (2026, 1)),
        ("2026-12", (2026, 12)),
        ("1999-09", (1999, 9)),
    ],
)
def test_parse_month_accepts_valid_strings(
    value: str, expected: tuple
) -> None:
    assert parse_month(value) == expected


@pytest.mark.parametrize(
    "bad",
    [
        "2026-13",  # month out of range
        "2026-00",  # month zero
        "2026/06",  # wrong separator
        "26-06",    # short year
        "june",     # words
        "2026-6",   # unpadded month
        "2026-06 ", # trailing space
        " 2026-06", # leading space
        "2026-06-01",  # full date
    ],
)
def test_parse_month_rejects_invalid_strings(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_month(bad)


@pytest.mark.parametrize("empty", [None, ""])
def test_parse_month_defaults_to_current_month(monkeypatch, empty) -> None:
    monkeypatch.setattr(
        "moco_filler.calendar_utils._today",
        lambda: date(2027, 3, 15),
    )
    assert parse_month(empty) == (2027, 3)


# ---------- weekday_dates ----------


def test_weekday_dates_excludes_weekends_in_june_2026() -> None:
    dates = weekday_dates(2026, 6)
    # June 2026 weekends: 6, 7, 13, 14, 20, 21, 27, 28.
    for weekend_day in (6, 7, 13, 14, 20, 21, 27, 28):
        assert date(2026, 6, weekend_day) not in dates
    # First weekday is Mon Jun 1, last is Tue Jun 30.
    assert dates[0] == date(2026, 6, 1)
    assert dates[-1] == date(2026, 6, 30)


def test_weekday_dates_all_have_weekday_index_under_5() -> None:
    dates = weekday_dates(2026, 6)
    assert all(d.weekday() < 5 for d in dates)


def test_weekday_dates_for_28_day_february_non_leap() -> None:
    # Feb 2027 has 28 days, non-leap. Weekdays = 20.
    dates = weekday_dates(2027, 2)
    assert len(dates) == 20


def test_weekday_dates_for_leap_year_february() -> None:
    # Feb 2028 has 29 days. Feb 1 2028 = Tue, Feb 29 2028 = Tue.
    dates = weekday_dates(2028, 2)
    assert len(dates) == 21
    assert date(2028, 2, 29) in dates


def test_weekday_dates_for_31_day_month() -> None:
    # July 2026: 31 days. Weekdays = 23.
    dates = weekday_dates(2026, 7)
    assert len(dates) == 23


def test_weekday_dates_handles_month_starting_on_weekend() -> None:
    # August 2026 starts on Saturday. First weekday is Mon Aug 3.
    dates = weekday_dates(2026, 8)
    assert dates[0] == date(2026, 8, 3)


def test_weekday_dates_handles_month_ending_on_weekend() -> None:
    # January 2027 ends Sunday Jan 31. Last weekday is Fri Jan 29.
    dates = weekday_dates(2027, 1)
    assert dates[-1] == date(2027, 1, 29)


def test_weekday_dates_returns_fresh_list() -> None:
    # Caller should be safe to mutate the returned list.
    dates_a = weekday_dates(2026, 6)
    dates_b = weekday_dates(2026, 6)
    dates_a.pop()
    assert dates_a != dates_b
