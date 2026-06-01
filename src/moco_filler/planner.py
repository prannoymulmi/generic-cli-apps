"""Build the preview's PlannedEntry list from a month + existing activities.

Implements the FR-005 "default 8h per weekday" baseline and the FR-012
cross-project existing-hours rule (sum across **all** projects/tasks,
lock at ≥ 8h, auto top-up to 8h on partial days).
"""

from __future__ import annotations

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
