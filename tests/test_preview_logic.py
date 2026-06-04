"""Pure-helper tests for moco_filler.preview.

Per ``specs/001-create-mvp-moco-filler-app/research.md`` §8, the live Questionary
loop is intentionally **not** unit-tested — these tests exercise only
the deterministic helpers (row format, label dispatch, running-total,
next-included-row).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import questionary

from moco_filler.models import PlannedEntry
from moco_filler.preview import (
    _build_choices,
    format_header,
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


# ---- US2 (feature 003 / 004): holiday state label dispatch -------------


def _holiday(d: date = date(2026, 5, 1)) -> PlannedEntry:
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


def test_state_label_holiday_row_shows_german_name() -> None:
    """A holiday auto-skipped row → ``[holiday: <name>]`` not ``[skipped]``."""
    assert state_label(_holiday()) == "[holiday: Tag der Arbeit]"


def test_state_label_holiday_plus_already_logged_uses_already_logged() -> None:
    """FR-005: already-logged wins, holiday name preserved as metadata only."""
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
    assert state_label(row) == "[already logged]"


def test_state_label_holiday_overridden_back_to_included_drops_label() -> None:
    """FR-006: re-including a holiday row removes the auto-skip label."""
    row = PlannedEntry(
        date=date(2026, 5, 1),
        weekday="Fri",
        existing_hours_total=Decimal("0"),
        hours=Decimal("8"),
        included=True,
        already_logged=False,
        note="Holiday: Tag der Arbeit",
        holiday_name="Tag der Arbeit",
    )
    # No `[holiday: ...]` — it's now a normal planned row.
    assert state_label(row) == "[planned]"


# ---------- format_row contracts/cli.md examples ----------


def test_format_row_plain_matches_preview_rendering_contract() -> None:
    row = _plain(date(2026, 6, 3))
    assert format_row(row) == "Wed  2026-06-03  8.00h  [planned]"


def test_format_row_top_up_matches_preview_rendering_contract() -> None:
    row = _top_up(date(2026, 6, 3))
    assert (
        format_row(row)
        == "Wed  2026-06-03  3.50h  [top-up: existing 4.50h]"
    )


def test_format_row_locked_matches_preview_rendering_contract() -> None:
    row = _locked(date(2026, 6, 3))
    assert format_row(row) == "Wed  2026-06-03  0.00h  [already logged]"


def test_format_row_skipped_matches_preview_rendering_contract() -> None:
    row = _skipped(date(2026, 6, 3))
    assert format_row(row) == "Wed  2026-06-03  8.00h  [skipped]"


# ---------- US1: column-alignment invariants (T001) ----------

# Column anchors derived from the contract's 2-space gap rule:
# Day starts at col 0, Date at 5, Hours at 17, State at 24.
_DAY_COL = 0
_DATE_COL = 3 + 2
_HOURS_COL = 3 + 2 + 10 + 2
_STATE_COL = 3 + 2 + 10 + 2 + 5 + 2


def test_format_row_day_column_is_three_chars_left_aligned() -> None:
    row = _plain(date(2026, 6, 3))
    rendered = format_row(row)
    assert rendered[_DAY_COL : _DAY_COL + 3] == "Wed"


def test_format_row_date_column_is_ten_chars_left_aligned() -> None:
    row = _plain(date(2026, 6, 3))
    rendered = format_row(row)
    assert rendered[_DATE_COL : _DATE_COL + 10] == "2026-06-03"


def test_format_row_hours_column_is_five_chars_right_aligned() -> None:
    row = _plain(date(2026, 6, 3))
    rendered = format_row(row)
    assert rendered[_HOURS_COL : _HOURS_COL + 5] == "8.00h"


def test_format_row_state_column_starts_at_same_position_across_states() -> None:
    """US1.AC-3: every state label opens at the same screen column."""
    rows = [
        _plain(date(2026, 6, 1)),
        _top_up(date(2026, 6, 2)),
        _locked(date(2026, 6, 3)),
        _skipped(date(2026, 6, 4)),
    ]
    for row in rows:
        rendered = format_row(row)
        assert (
            rendered[_STATE_COL] == "["
        ), f"State '[' not at col {_STATE_COL} for {row!r}: {rendered!r}"


def test_format_row_gaps_are_exactly_two_spaces() -> None:
    """Per contracts/preview-rendering.md — no single-space or tab gaps."""
    rendered = format_row(_plain(date(2026, 6, 3)))
    # Slice out each 2-char gap between columns:
    assert rendered[3:5] == "  "  # gap after Day
    assert rendered[15:17] == "  "  # gap after Date
    assert rendered[22:24] == "  "  # gap after Hours


# ---------- US1: format_header anchors (T002) ----------


def test_format_header_returns_aligned_header_string() -> None:
    header = format_header()
    assert header[_DAY_COL : _DAY_COL + 3] == "Day"
    assert header[_DATE_COL : _DATE_COL + 4] == "Date"
    assert header[_HOURS_COL : _HOURS_COL + 5] == "Hours"
    assert header[_STATE_COL : _STATE_COL + 5] == "State"


def test_format_header_columns_align_with_format_row() -> None:
    """FR-002: header columns sit directly above their data-row counterparts."""
    header = format_header()
    row = format_row(_plain(date(2026, 6, 3)))
    # Same starting column for Day / Date / Hours / State markers.
    assert header.index("Day") == row.index("Wed")
    assert header.index("Date") == row.index("2026-06-03")
    assert header.index("Hours") == row.index("8.00h")
    assert header.index("State") == row.index("[planned]")


# ---------- US1: _build_choices prepends header Separator (T003) ----------


def test_build_choices_first_item_is_header_separator() -> None:
    entries = [_plain(date(2026, 6, 1)), _plain(date(2026, 6, 2))]
    items = _build_choices(entries)
    assert isinstance(items[0], questionary.Separator)
    # The Separator carries the header text — read via its .line attribute
    # (prompt_toolkit's Separator exposes the line both as .line and .title).
    assert items[0].title == format_header()


def test_build_choices_data_rows_follow_header() -> None:
    entries = [_plain(date(2026, 6, 1)), _plain(date(2026, 6, 2))]
    items = _build_choices(entries)
    # items[0] is the header Separator; items[1..] should be data rows
    # (Choice objects, not Separators) for each entry.
    assert isinstance(items[1], questionary.Choice)
    assert isinstance(items[2], questionary.Choice)


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
