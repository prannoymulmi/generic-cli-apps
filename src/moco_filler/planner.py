"""Build and edit the preview's PlannedEntry list.

Implements the FR-005 "default 8h per weekday" baseline and the FR-012
cross-project existing-hours rule (sum across **all** projects/tasks,
lock at ≥ 8h, auto top-up to 8h on partial days). ``toggle_skipped``
and ``set_hours`` are the pure US3 row-edit primitives — kept here so
the preview UI can stay free of business rules per ``research.md`` §8.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Mapping, Optional

from moco_filler.calendar_utils import weekday_dates
from moco_filler.models import (
    DAY_FULL_THRESHOLD,
    HOURS_CAP,
    HOURS_FLOOR,
    PlannedEntry,
)


def build_planned_entries(
    year: int,
    month: int,
    existing_activities: Iterable[Dict[str, Any]],
    holiday_catalogue: Optional[Mapping[date, str]] = None,
) -> List[PlannedEntry]:
    """Return one PlannedEntry per Mon-Fri date in ``year-month``.

    ``existing_activities`` is the raw list ``MocoClient.get_activities``
    returns — each record needs at least ``date`` (``YYYY-MM-DD``) and
    ``hours`` (number). Records whose date doesn't fall on a weekday of
    the chosen month are silently ignored.

    ``holiday_catalogue`` (feature 003 / 004) maps ``date → German
    holiday name`` for the dates the CLI should auto-skip as Hamburg
    public holidays. An empty / ``None`` mapping is the FR-007 /
    FR-013 graceful fallback — the planner produces the same shape it
    did before holidays existed. Already-logged rows take precedence
    over the holiday-skip per FR-005: the row stays locked but
    ``holiday_name`` is preserved as metadata.
    """
    totals = _sum_hours_per_date(existing_activities)
    catalogue: Mapping[date, str] = holiday_catalogue or {}
    return [
        _build_one(d, totals.get(d, Decimal("0")), catalogue.get(d))
        for d in weekday_dates(year, month)
    ]


def _sum_hours_per_date(
    activities: Iterable[Dict[str, Any]],
) -> Dict[date, Decimal]:
    totals: Dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    for activity in activities:
        d = _parse_activity_date(activity.get("date"))
        if d is None:
            continue
        totals[d] += _parse_activity_hours(activity.get("hours"))
    return dict(totals)


def _parse_activity_date(raw: Any) -> Optional[date]:
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_activity_hours(raw: Any) -> Decimal:
    if raw is None:
        return Decimal("0")
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _build_one(
    d: date,
    existing_total: Decimal,
    holiday_name: Optional[str] = None,
) -> PlannedEntry:
    weekday = d.strftime("%a")

    if existing_total >= DAY_FULL_THRESHOLD:
        # FR-005 precedence: already-logged wins, holiday metadata preserved.
        return PlannedEntry(
            date=d,
            weekday=weekday,
            existing_hours_total=existing_total,
            hours=HOURS_FLOOR,
            included=False,
            already_logged=True,
            note=f"Already logged ({_fmt(existing_total)}h, day full)",
            holiday_name=holiday_name,
        )

    if holiday_name is not None:
        # FR-002 + FR-003: auto-skipped Hamburg public holiday.
        return PlannedEntry(
            date=d,
            weekday=weekday,
            existing_hours_total=existing_total,
            hours=HOURS_FLOOR,
            included=False,
            already_logged=False,
            note=f"Holiday: {holiday_name}",
            holiday_name=holiday_name,
        )

    if existing_total > HOURS_FLOOR:
        return PlannedEntry(
            date=d,
            weekday=weekday,
            existing_hours_total=existing_total,
            hours=HOURS_CAP - existing_total,
            included=True,
            already_logged=False,
            note=f"Top-up: existing {_fmt(existing_total)}h",
        )

    return PlannedEntry(
        date=d,
        weekday=weekday,
        existing_hours_total=Decimal("0"),
        hours=HOURS_CAP,
        included=True,
        already_logged=False,
        note=None,
    )


def _fmt(value: Decimal) -> str:
    """Two-decimal rendering matching contracts/cli.md preview format."""
    return f"{value:.2f}"


# ---- US3 row-edit helpers (pure; no UI imports) -------------------------


def toggle_skipped(row: PlannedEntry) -> PlannedEntry:
    """Flip a row's ``included`` flag (FR-008).

    Already-logged rows are locked (FR-012); toggling them raises
    ``ValueError`` so callers can't quietly bypass the lock.

    Holiday rows (``holiday_name is not None``) get one extra rule
    from feature 003 US3:

    - Re-including a holiday row restores the default hours
      (``HOURS_CAP`` minus any pre-existing logged total, exactly as
      :func:`build_planned_entries` would produce fresh), so the row
      becomes submitable at the expected default (US3 AC-1).
    - Re-skipping a re-included holiday row resets hours to 0 so the
      row returns to its canonical auto-skipped shape (FR-007), not a
      generic user-skipped row.

    Non-holiday rows keep the original behaviour — :func:`dataclasses.replace`
    preserves ``hours`` across the toggle so a user's prior
    ``Change hours`` edit isn't dropped on skip.
    """
    if row.already_logged:
        raise ValueError(
            "Cannot toggle an already-logged row (FR-012)"
        )
    if row.holiday_name is not None:
        if row.included:
            # Re-skip: back to canonical holiday-auto-skip shape.
            return dataclasses.replace(
                row, included=False, hours=HOURS_FLOOR
            )
        # Re-include: restore default hours (top-up shape or full day).
        if row.existing_hours_total > HOURS_FLOOR:
            new_hours = HOURS_CAP - row.existing_hours_total
        else:
            new_hours = HOURS_CAP
        return dataclasses.replace(row, included=True, hours=new_hours)
    return dataclasses.replace(row, included=not row.included)


def set_hours(row: PlannedEntry, value: Decimal) -> PlannedEntry:
    """Set ``hours`` on a row within the FR-008 ``[0, 8]`` range.

    Setting ``value == 0`` auto-skips the row (Q2 clarification,
    2026-06-01). Already-logged rows are locked (FR-012) and refuse
    edits.
    """
    if row.already_logged:
        raise ValueError(
            "Cannot change hours on an already-logged row (FR-012)"
        )
    if not (HOURS_FLOOR <= value <= HOURS_CAP):
        raise ValueError(
            f"hours must be within [{HOURS_FLOOR}, {HOURS_CAP}]; got {value}"
        )
    if value == HOURS_FLOOR:
        return dataclasses.replace(row, hours=value, included=False)
    return dataclasses.replace(row, hours=value)
