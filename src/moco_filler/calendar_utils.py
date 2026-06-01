"""Date helpers — month parsing + weekday enumeration.

Stdlib only (``datetime`` + ``calendar``) per ``research.md`` §4. No
third-party date libraries are introduced.
"""

from __future__ import annotations

import calendar
import re
from datetime import date
from typing import List, Optional, Tuple


_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _today() -> date:
    """Indirection so tests can pin "now" without monkeypatching ``date``."""
    return date.today()


def parse_month(value: Optional[str]) -> Tuple[int, int]:
    """Parse a ``YYYY-MM`` string into ``(year, month)``.

    Passing ``None`` or an empty string yields the current calendar
    month at the moment of the call (FR-002). Invalid formats raise
    ``ValueError``; the caller maps that to exit code ``1``.
    """
    if not value:
        today = _today()
        return today.year, today.month

    if not _MONTH_RE.match(value):
        raise ValueError(
            f"Invalid --month value {value!r}; expected YYYY-MM "
            "(e.g., 2026-06)"
        )

    year_str, month_str = value.split("-", 1)
    return int(year_str), int(month_str)


def weekday_dates(year: int, month: int) -> List[date]:
    """Return every Mon-Fri date in ``year-month`` in ascending order.

    Weekends are excluded at construction time per FR-005 and FR-014.
    The returned list is fresh and safe for the caller to mutate.
    """
    _, days_in_month = calendar.monthrange(year, month)
    return [
        date(year, month, day)
        for day in range(1, days_in_month + 1)
        if date(year, month, day).weekday() < 5
    ]
