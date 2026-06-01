"""Questionary-driven preview of the month's planned entries.

US1 ships a **read-only** preview: the user navigates with the arrow
keys (Questionary's ``select`` highlights the focused row natively per
FR-007), and chooses either ``Approve & submit`` or ``Cancel``.
Per-row Skip / Change-hours editing is added by US3 (see T030).

The pure formatting helpers (``format_row`` / ``state_label``) are
exposed for unit testing per ``research.md`` §8. The live Questionary
loop is intentionally not unit-tested.
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Literal

import questionary

from moco_filler.models import PlannedEntry


APPROVE_VALUE = "__approve__"
CANCEL_VALUE = "__cancel__"

PreviewDecision = Literal["approve", "cancel"]


def show_preview(entries: List[PlannedEntry]) -> PreviewDecision:
    """Show the preview and return ``"approve"`` or ``"cancel"``.

    Selecting a data row in this read-only version simply re-prompts —
    US3 wires that selection up to the per-row sub-menu.
    Ctrl-C / Esc returns ``"cancel"`` (Questionary's ``ask`` yields
    ``None`` in that case).
    """
    while True:
        choice = questionary.select(
            "Review the planned entries:",
            choices=_build_choices(entries),
        ).ask()

        if choice == APPROVE_VALUE:
            return "approve"
        if choice in (CANCEL_VALUE, None):
            return "cancel"
        # Data-row selection in read-only mode → re-prompt silently.


def _build_choices(entries: List[PlannedEntry]) -> list:
    """Return the Questionary choices list (rows + separator + actions)."""
    items: list = [
        questionary.Choice(
            title=format_row(entry),
            value=entry.date.isoformat(),
        )
        for entry in entries
    ]
    items.append(questionary.Separator())
    items.append(questionary.Choice(title="✅ Approve & submit", value=APPROVE_VALUE))
    items.append(questionary.Choice(title="❌ Cancel", value=CANCEL_VALUE))
    return items


# ---- pure helpers (importable for tests in T028) ------------------------


def format_row(entry: PlannedEntry) -> str:
    """Render one PlannedEntry as the columnar choice string.

    Matches the format examples in
    ``specs/001-moco-time-tracker/contracts/cli.md`` § "Interactive flow".
    """
    return (
        f"{entry.weekday} {entry.date.isoformat()}   "
        f"{entry.hours:>4.2f}h   {state_label(entry)}"
    )


def state_label(entry: PlannedEntry) -> str:
    """Return the bracketed state suffix for a preview row."""
    if entry.already_logged:
        return "[already logged]"
    if not entry.included:
        return "[skipped]"
    if entry.existing_hours_total > Decimal("0"):
        return f"[top-up: existing {entry.existing_hours_total:.2f}h]"
    return "[planned]"
