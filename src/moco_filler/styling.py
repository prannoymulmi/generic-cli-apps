"""Visual policy for moco-filler — palette, colour detection, row formatter.

Owns every styling decision in one place per Constitution §V so
``preview.py`` / ``cli.py`` stay orchestration-only and a future palette
tweak lives in exactly one file. Built on top of Questionary's existing
``style=`` parameter (a prompt_toolkit ``Style.from_dict``) and the
FormattedText ``(class, text)`` choice-title shape Questionary already
accepts — no new top-level dependency (FR-009).

When :func:`is_color_enabled` returns ``False`` (``NO_COLOR`` set,
``TERM=dumb``, or stdout isn't a TTY), the formatters fall back to
plain strings and :func:`get_style` returns ``None`` so call sites can
omit the ``style=`` kwarg entirely — keeping the captured output free
of stray ANSI escapes (FR-007, SC-004).

US3 extends this module with the cursor pointer glyph, the
``highlighted`` reverse-video chrome, and the Approve/Cancel action
classes; US2 ships only the per-state palette below.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from typing import List, Optional, Tuple, Union

from prompt_toolkit.styles import Style

from moco_filler.models import PlannedEntry


FormattedText = List[Tuple[str, str]]
StyledText = Union[str, FormattedText]


# ---- colour detection ---------------------------------------------------


def _is_tty() -> bool:
    """Wrapper around ``sys.stdout.isatty()`` — extracted so tests can
    monkeypatch the TTY check without replacing pytest's captured stdout.
    """
    return sys.stdout.isatty()


def is_color_enabled() -> bool:
    """``True`` when colour should be emitted for this run.

    Triggers for monochrome (any one of):

    1. ``NO_COLOR`` env var set to a non-empty (post-strip) value per
       the cross-platform `no-color.org`_ convention.
    2. ``TERM`` env var equals ``"dumb"``.
    3. ``sys.stdout`` is not a TTY (piped, redirected, CI logs).
    """
    if os.environ.get("NO_COLOR", "").strip():
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    if not _is_tty():
        return False
    return True


# ---- palette ------------------------------------------------------------


_PALETTE: dict = {
    "row.header": "bold underline",
    "row.planned": "fg:#5fafff",        # soft cyan — default-8h weekday
    "row.topup": "fg:#ffd75f",          # yellow — partial day top-up
    "row.locked": "fg:#808080",         # dim grey — already logged
    "row.skipped": "fg:#af5f5f",        # dim red — user-skipped row
}


def build_style() -> Optional[Style]:
    """Assemble the prompt_toolkit ``Style`` for this run.

    Returns ``None`` when colour is disabled so call sites can omit
    ``style=`` entirely. Chrome classes (``pointer``, ``highlighted``,
    ``action.*``) are added by US3.
    """
    if not is_color_enabled():
        return None
    return Style.from_dict(dict(_PALETTE))


_cached_style: Optional[Style] = None
_cache_computed: bool = False


def get_style() -> Optional[Style]:
    """Lazy cache around :func:`build_style` — assembled once per run."""
    global _cached_style, _cache_computed
    if not _cache_computed:
        _cached_style = build_style()
        _cache_computed = True
    return _cached_style


def _reset_cache() -> None:
    """Test hook — clear the cached Style between tests."""
    global _cached_style, _cache_computed
    _cached_style = None
    _cache_computed = False


def select_kwargs() -> dict:
    """Return ``{"style": Style}`` when colour is enabled, else ``{}``.

    Use as ``questionary.select(..., **select_kwargs())`` so the
    ``style=`` kwarg is omitted entirely when colour is disabled
    (no ``style=None`` leaks — see `contracts/preview-rendering.md`
    § Monochrome fallback). US3 extends this with the ``pointer``
    kwarg so the focused-row marker is reinforced beyond colour
    alone.
    """
    style = get_style()
    return {"style": style} if style is not None else {}


# ---- pure row / header / label formatters -------------------------------
# Lives here so `styling.py` owns every visual decision in one place
# (Constitution §V). `preview.py` re-exports these so existing test
# imports stay valid.


def state_label(entry: PlannedEntry) -> str:
    """Return the bracketed state suffix for a preview row."""
    if entry.already_logged:
        return "[already logged]"
    if not entry.included:
        return "[skipped]"
    if entry.existing_hours_total > Decimal("0"):
        return f"[top-up: existing {entry.existing_hours_total:.2f}h]"
    return "[planned]"


def format_row(entry: PlannedEntry) -> str:
    """Render one PlannedEntry as the columnar choice string.

    Column layout per
    ``specs/002-add-coloring-and-spacing-to-the-app/contracts/preview-rendering.md``:
    Day=3 left, Date=10 left, Hours=5 right, State=flex left, with a
    literal two-space gap between every column.
    """
    hours_str = f"{entry.hours:.2f}h"
    return (
        f"{entry.weekday:<3}  "
        f"{entry.date.isoformat():<10}  "
        f"{hours_str:>5}  "
        f"{state_label(entry)}"
    )


def format_header() -> str:
    """Header row matching :func:`format_row`'s column anchors (US1.AC-2)."""
    return (
        f"{'Day':<3}  "
        f"{'Date':<10}  "
        f"{'Hours':>5}  "
        f"State"
    )


def _row_class(entry: PlannedEntry) -> str:
    """Map a PlannedEntry's state to the matching ``row.*`` class.

    The four arms are mutually exclusive for any valid PlannedEntry
    (see ``data-model.md`` § RowPresentation).
    """
    if entry.already_logged:
        return "row.locked"
    if not entry.included:
        return "row.skipped"
    if entry.existing_hours_total > Decimal("0"):
        return "row.topup"
    return "row.planned"


def format_styled_row(entry: PlannedEntry) -> StyledText:
    """Return a styled choice title for a PlannedEntry.

    FormattedText tuple list when colour is enabled; a plain string
    (identical to :func:`format_row`) when colour is disabled.
    """
    text = format_row(entry)
    if not is_color_enabled():
        return text
    return [(f"class:{_row_class(entry)}", text)]


def format_styled_header() -> StyledText:
    """Return a styled choice title for the column-header row."""
    text = format_header()
    if not is_color_enabled():
        return text
    return [("class:row.header", text)]
