# Data Model: Table-Styled Preview for moco-filler

**Feature**: 002-add-coloring-and-spacing-to-the-app

**Date**: 2026-06-01

This feature introduces no new domain entities. Every existing
dataclass from `specs/001-create-mvp-moco-filler-app/data-model.md`
(`ApiCredentials`, `Project`, `Task`, `PlannedEntry`,
`SubmissionBatch`, `EntryResult`, `SubmissionResult`) is reused
unchanged.

The only new concept is a **Row presentation** — a derived view of an
existing `PlannedEntry` produced at render time and discarded between
keystrokes. It lives in memory only and never crosses a module
boundary other than the Questionary call site.

---

## `RowPresentation` (transient, in-memory)

Produced by `styling.format_styled_row(entry)` (or its monochrome
sibling `format_row(entry)` in `preview.py`). Two shapes, chosen by the
`is_color_enabled()` predicate:

| Mode | Type | Notes |
|------|------|-------|
| **Colour** | `list[tuple[str, str]]` | prompt_toolkit FormattedText — each tuple is `(style_class, text_fragment)`. |
| **Monochrome** | `str` | Plain pre-padded line; column alignment preserved. |

A row's `style_class` is derived from its `PlannedEntry` state:

| `PlannedEntry` state | `style_class` |
|----------------------|---------------|
| `already_logged == True` | `row.locked` |
| `included == False` (and not locked) | `row.skipped` |
| `included == True and existing_hours_total > 0` | `row.topup` |
| `included == True and existing_hours_total == 0` | `row.planned` |

These four states are mutually exclusive and exhaustive for any valid
`PlannedEntry`, so the dispatch is a four-arm conditional with no
fallback branch.

**Validation**:

- The derived view MUST NOT mutate the underlying `PlannedEntry`.
- A row's `style_class` MUST match exactly one of the four values
  above; an unrecognised state is a logic error.

---

## `HeaderPresentation` (transient, in-memory)

The single non-selectable line at the top of the preview, produced by
`styling.format_header()`. Same two-shape rule as `RowPresentation` —
FormattedText list in colour mode, plain string in monochrome — and
the column anchors MUST match those of the data rows so the table
visually aligns (FR-002).

**Validation**: the string width of every column in the header MUST
equal the width of the same column in every data row produced by
`format_styled_row()` for the same colour mode.

---

## `ActionPresentation` (transient, in-memory)

The styled title for the two non-row actions: `Approve & submit` and
`Cancel`. Produced by `styling.format_action(label, kind)` where
`kind` is `"approve"` or `"cancel"`. Both shapes (colour /
monochrome) supported as above.

`style_class` mapping:

| `kind` | `style_class` |
|--------|---------------|
| `"approve"` | `action.approve` |
| `"cancel"` | `action.cancel` |

---

## Relationships

```
PlannedEntry (existing, unchanged)
   │
   ▼
styling.is_color_enabled()  ──► bool (env + TTY check)
   │
   ▼
styling.format_styled_row(entry)  /  preview.format_row(entry)
   │
   ▼
questionary.Choice(title=RowPresentation, value=<row index>)
   │
   ▼
questionary.select(..., style=build_style())  ◀── all rows + header + actions
```

The data flow is one-way: a `PlannedEntry` produces a
`RowPresentation`; nothing in the styling module reads back into the
domain model.

---

## Lifetime

`RowPresentation`, `HeaderPresentation`, and `ActionPresentation`
values live for one repaint of the Questionary preview and are
discarded immediately afterwards. No caching, no memoisation — the
preview re-runs `_build_choices` after every accepted edit anyway, and
the formatter cost is negligible at ~23 rows per repaint.

The assembled `Style` object from `build_style()` is built once at
process start in `cli.main()` and passed by reference into every
Questionary call for the lifetime of the run.
