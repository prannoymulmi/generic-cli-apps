"""Pure-helper tests for moco_filler.preview.

Per ``specs/001-moco-time-tracker/research.md`` §8, the live Questionary
loop is intentionally **not** unit-tested — these tests exercise only
the deterministic helpers (row format, label dispatch, running-total,
next-included-row).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from moco_filler.models import PlannedEntry
from moco_filler.preview import (
    format_row,
    next_included_row,
    running_total,
    state_label,
)


# ---------- helpers ----------


def _plain(d: date = date(2026, 6, 3)) -> PlannedEntry:
    return PlannedEntry(
        date=d,
        weekday=d.strftime("%a"),
        existing_hours_total=Decimal("0"),
        hours=Decimal("8"),
        included=True,
        already_logged=False,
        note=None,
    )


def _top_up(d: date = date(2026, 6, 4)) -> PlannedEntry:
    return PlannedEntry(
        date=d,
        weekday=d.strftime("%a"),
        existing_hours_total=Decimal("4.5"),
        hours=Decimal("3.5"),
        included=True,
        already_logged=False,
        note="Top-up: existing 4.50h",
    )


def _locked(d: date = date(2026, 6, 5)) -> PlannedEntry:
    return PlannedEntry(
        date=d,
        weekday=d.strftime("%a"),
        existing_hours_total=Decimal("8"),
        hours=Decimal("0"),
        included=False,
        already_logged=True,
        note="Already logged (8.00h, day full)",
    )


def _skipped(d: date = date(2026, 6, 8)) -> PlannedEntry:
    return PlannedEntry(
        date=d,
        weekday=d.strftime("%a"),
        existing_hours_total=Decimal("0"),
        hours=Decimal("8"),
        included=False,  # user toggled off
        already_logged=False,
        note=None,
    )


# ---------- state_label dispatch (one case per state) ----------


def test_state_label_plain_row() -> None:
    assert state_label(_plain()) == "[planned]"


def test_state_label_top_up_row() -> None:
    assert state_label(_top_up()) == "[top-up: existing 4.50h]"


def test_state_label_already_logged_row() -> None:
    # Even if existing_hours_total > 0 and included is False, the
    # already_logged label wins (FR-012 lock takes precedence).
    assert state_label(_locked()) == "[already logged]"


def test_state_label_skipped_row() -> None:
    assert state_label(_skipped()) == "[skipped]"


# ---------- format_row contracts/cli.md examples ----------


def test_format_row_plain_matches_cli_md_example() -> None:
    row = _plain(date(2026, 6, 3))
    assert format_row(row) == "Wed 2026-06-03   8.00h   [planned]"


def test_format_row_top_up_matches_cli_md_example() -> None:
    row = _top_up(date(2026, 6, 3))
    assert (
        format_row(row)
        == "Wed 2026-06-03   3.50h   [top-up: existing 4.50h]"
    )


def test_format_row_locked_matches_cli_md_example() -> None:
    row = _locked(date(2026, 6, 3))
    assert format_row(row) == "Wed 2026-06-03   0.00h   [already logged]"


def test_format_row_skipped_matches_cli_md_example() -> None:
    row = _skipped(date(2026, 6, 3))
    assert format_row(row) == "Wed 2026-06-03   8.00h   [skipped]"


# ---------- running_total ----------


def test_running_total_sums_submitable_rows_only() -> None:
    total = running_total(
        [_plain(date(2026, 6, 1)), _top_up(date(2026, 6, 2))]
    )
    assert total == Decimal("11.5")


def test_running_total_excludes_skipped_rows() -> None:
    total = running_total(
        [_plain(date(2026, 6, 1)), _skipped(date(2026, 6, 2))]
    )
    assert total == Decimal("8")


def test_running_total_excludes_already_logged_rows() -> None:
    total = running_total(
        [_plain(date(2026, 6, 1)), _locked(date(2026, 6, 2))]
    )
    assert total == Decimal("8")


def test_running_total_empty_list_is_zero() -> None:
    assert running_total([]) == Decimal("0")


# ---------- next_included_row ----------


def test_next_included_row_returns_next_editable_index() -> None:
    rows = [
        _plain(date(2026, 6, 1)),
        _plain(date(2026, 6, 2)),
        _plain(date(2026, 6, 3)),
    ]
    assert next_included_row(rows, 0) == 1


def test_next_included_row_skips_locked_rows() -> None:
    rows = [
        _plain(date(2026, 6, 1)),
        _locked(date(2026, 6, 2)),
        _plain(date(2026, 6, 3)),
    ]
    # From index 0 the next editable row is at index 2 (1 is locked).
    assert next_included_row(rows, 0) == 2


def test_next_included_row_returns_none_at_end_of_list() -> None:
    rows = [_plain(date(2026, 6, 1)), _plain(date(2026, 6, 2))]
    assert next_included_row(rows, 1) is None


def test_next_included_row_returns_none_when_only_locked_remain() -> None:
    rows = [
        _plain(date(2026, 6, 1)),
        _locked(date(2026, 6, 2)),
        _locked(date(2026, 6, 3)),
    ]
    assert next_included_row(rows, 0) is None


def test_next_included_row_returns_none_for_empty_list() -> None:
    assert next_included_row([], 0) is None
