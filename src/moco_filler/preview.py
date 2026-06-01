"""Questionary-driven preview of the month's planned entries.

US1 (T018) shipped the read-only navigation + Approve / Cancel actions;
US3 (T030) adds the per-row sub-menu — Skip / Include / Change hours —
plus a running submit-total in the prompt so the user can see edits
update in real time (FR-008). Already-logged rows stay locked (FR-012).

The pure helpers (``format_row``, ``state_label``, ``running_total``,
``next_included_row``) are exposed for unit testing per ``research.md``
§8. The live Questionary loop is intentionally not unit-tested.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import List, Literal, Optional

import questionary

from moco_filler.models import PlannedEntry
from moco_filler.planner import set_hours, toggle_skipped


APPROVE_VALUE = "__approve__"
CANCEL_VALUE = "__cancel__"
BACK_VALUE = "__back__"
SKIP_VALUE = "__skip__"
INCLUDE_VALUE = "__include__"
CHANGE_HOURS_VALUE = "__change_hours__"

PreviewDecision = Literal["approve", "cancel"]


def show_preview(entries: List[PlannedEntry]) -> PreviewDecision:
    """Show the preview and return ``"approve"`` or ``"cancel"``.

    Mutates ``entries`` in place when the user accepts a per-row edit.
    Ctrl-C / Esc at any prompt returns ``"cancel"`` per
    ``contracts/cli.md`` § Interactive flow.
    """
    while True:
        choice = questionary.select(
            _preview_prompt(entries),
            choices=_build_choices(entries),
        ).ask()

        if choice == APPROVE_VALUE:
            return "approve"
        if choice in (CANCEL_VALUE, None):
            return "cancel"

        # Data-row index — open the per-row sub-menu.
        if _edit_row(entries, int(choice)) == "cancel":
            return "cancel"


def _preview_prompt(entries: List[PlannedEntry]) -> str:
    total = running_total(entries)
    return f"Review the planned entries (will submit {total:.2f}h):"


def _build_choices(entries: List[PlannedEntry]) -> list:
    """Return the Questionary choices list (rows + separator + actions)."""
    items: list = [
        questionary.Choice(title=format_row(entry), value=index)
        for index, entry in enumerate(entries)
    ]
    items.append(questionary.Separator())
    items.append(
        questionary.Choice(title="✅ Approve & submit", value=APPROVE_VALUE)
    )
    items.append(questionary.Choice(title="❌ Cancel", value=CANCEL_VALUE))
    return items


def _edit_row(
    entries: List[PlannedEntry], index: int
) -> Optional[Literal["cancel"]]:
    """Open the sub-menu for ``entries[index]`` and apply any edit.

    Returns ``"cancel"`` when the user aborts via Ctrl-C / Esc so the
    caller can bubble cancellation up; ``None`` otherwise.
    """
    row = entries[index]

    if row.already_logged:
        # FR-012: locked row sub-menu is "Back only".
        result = questionary.select(
            f"{format_row(row)} — locked (already logged)",
            choices=[questionary.Choice(title="Back", value=BACK_VALUE)],
        ).ask()
        return "cancel" if result is None else None

    action = questionary.select(
        f"{format_row(row)} — choose an action:",
        choices=_row_actions(row),
    ).ask()

    if action is None:
        return "cancel"
    if action == BACK_VALUE:
        return None
    if action in (SKIP_VALUE, INCLUDE_VALUE):
        entries[index] = toggle_skipped(row)
        return None
    if action == CHANGE_HOURS_VALUE:
        new_hours = _prompt_hours(row)
        if new_hours is None:
            return "cancel"
        entries[index] = set_hours(row, new_hours)
        return None
    return None


def _row_actions(row: PlannedEntry) -> list:
    actions: list = []
    if row.included:
        actions.append(
            questionary.Choice(title="Skip this row", value=SKIP_VALUE)
        )
    else:
        actions.append(
            questionary.Choice(
                title="Include this row", value=INCLUDE_VALUE
            )
        )
    actions.append(
        questionary.Choice(title="Change hours", value=CHANGE_HOURS_VALUE)
    )
    actions.append(questionary.Choice(title="Back", value=BACK_VALUE))
    return actions


def _prompt_hours(row: PlannedEntry) -> Optional[Decimal]:
    answer = questionary.text(
        f"Hours for {row.date.isoformat()} (0–8):",
        default=f"{row.hours}",
        validate=_validate_hours,
    ).ask()
    if answer is None:
        return None
    return Decimal(answer.strip())


def _validate_hours(value: str):
    text = (value or "").strip()
    if not text:
        return "Enter a number between 0 and 8"
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return "Enter a numeric value like 4 or 4.5"
    if parsed < Decimal("0") or parsed > Decimal("8"):
        return "Hours must be between 0 and 8"
    return True


# ---- pure helpers (importable for tests) --------------------------------


def format_row(entry: PlannedEntry) -> str:
    """Render one PlannedEntry as the columnar choice string.

    Matches the format examples in
    ``specs/001-moco-time-tracker/contracts/cli.md`` § Interactive flow.
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


def running_total(entries: List[PlannedEntry]) -> Decimal:
    """Sum of hours that will be sent to Moco on approval.

    Only ``is_submitable`` rows contribute (FR-008 + FR-012): skipped
    rows, locked already-logged rows, and rows whose hours dropped to
    zero are excluded.
    """
    total = Decimal("0")
    for entry in entries:
        if entry.is_submitable:
            total += entry.hours
    return total


def next_included_row(
    entries: List[PlannedEntry], current_index: int
) -> Optional[int]:
    """Index of the next non-locked row after ``current_index``.

    Used to point focus at a still-editable row after a re-render.
    Already-logged rows are skipped (FR-012); returns ``None`` when no
    editable row remains in the tail.
    """
    for i in range(current_index + 1, len(entries)):
        if not entries[i].already_logged:
            return i
    return None
