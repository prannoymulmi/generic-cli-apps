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
from typing import Any, Dict, Iterable, List, Optional

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
) -> List[PlannedEntry]:
    """Return one PlannedEntry per Mon-Fri date in ``year-month``.

    ``existing_activities`` is the raw list ``MocoClient.get_activities``
    returns — each record needs at least ``date`` (``YYYY-MM-DD``) and
    ``hours`` (number). Records whose date doesn't fall on a weekday of
    the chosen month are silently ignored: they can't influence any
    PlannedEntry that exists, and the API may return adjacent rows on
    boundary days.
    """
    totals = _sum_hours_per_date(existing_activities)
    return [
        _build_one(d, totals.get(d, Decimal("0")))
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


def _build_one(d: date, existing_total: Decimal) -> PlannedEntry:
    weekday = d.strftime("%a")

    if existing_total >= DAY_FULL_THRESHOLD:
        return PlannedEntry(
            date=d,
            weekday=weekday,
            existing_hours_total=existing_total,
            hours=HOURS_FLOOR,
            included=False,
            already_logged=True,
            note=f"Already logged ({_fmt(existing_total)}h, day full)",
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
    """
    if row.already_logged:
        raise ValueError(
            "Cannot toggle an already-logged row (FR-012)"
        )
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
