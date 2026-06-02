# Contract: Preview Rendering

**Feature**: 002-add-coloring-and-spacing-to-the-app

**Date**: 2026-06-01

This is the **internal** rendering contract between `styling.py`,
`preview.py`, and the user-visible terminal. It is NOT a CLI surface —
the public CLI contract from
`specs/001-create-mvp-moco-filler-app/contracts/cli.md` (flags, stdout lines,
exit codes) is unchanged by this feature.

---

## Visual contract for the preview

When the user lands in the preview (after picking project + task),
the screen MUST be composed in this order, top to bottom:

1. The Questionary question line:
   `"Review the planned entries (will submit X.XXh):"` (unchanged
   from feature 001).
2. A **header row** (a `questionary.Separator` whose label is the
   formatted header) carrying the column labels `Day`, `Date`,
   `Hours`, `State` aligned under their data-row columns below.
3. One **data row** per weekday in the chosen month, in ascending
   date order, with the four columns aligned with the header.
4. A `questionary.Separator` line (no label) above the actions.
5. The `Approve & submit` action choice (styled green when colour is
   enabled).
6. The `Cancel` action choice (styled red when colour is enabled).

Exactly one of the data rows or action choices is focused at any
moment. The focused entry receives the left-edge pointer (`▶ ` when
colour is enabled; Questionary's default `»` when colour is
disabled) AND a reverse-video background.

---

## Column layout (FR-001, FR-002, FR-003)

| Column | Min width | Alignment | Worst-case content |
|--------|-----------|-----------|--------------------|
| `Day` | 3 chars | left | `Wed` |
| `Date` | 10 chars | left | `2026-06-03` |
| `Hours` | 5 chars | right | `8.00h` |
| `State` | flex | left | `[top-up: existing 7.75h]` |

**Gap between columns**: two literal spaces. No tab characters, no
single-space gaps.

The header row uses the same widths and gap, with the literal labels
`Day`, `Date`, `Hours`, `State`.

A data row example (monochrome, after f-string formatting):

```
Wed  2026-06-03   3.50h  [top-up: existing 4.50h]
```

Header row (monochrome):

```
Day  Date         Hours  State
```

The screen-column position of `D` in `Date`, of `H` in `Hours`, and
of `S` in `State` MUST be identical in the header and every data row.

---

## Colour palette (FR-005)

When colour is enabled, every visible element is rendered through one
of these prompt_toolkit `Style.from_dict` classes (all defined in
`styling.py`):

| Class | Applied to | Suggested colour |
|-------|------------|------------------|
| `row.header` | the header `Separator` | bold underline default-fg |
| `row.planned` | a default-8h weekday row | cyan |
| `row.topup` | a partial-day row | yellow |
| `row.locked` | an already-logged row | dim grey |
| `row.skipped` | a user-skipped row | dim red |
| `action.approve` | the `Approve & submit` choice | bright green bold |
| `action.cancel` | the `Cancel` choice | bright red bold |
| `pointer` | Questionary chrome — focused-row prefix | bright green bold |
| `highlighted` | Questionary chrome — focused row text | reverse |
| `qmark` | Questionary chrome — leading `?` | bright green bold |
| `separator` | Questionary chrome — empty separator | grey |
| `instruction` | Questionary chrome — keybinding hint | dim |
| `selected` | Questionary chrome — confirmed pick | bright green |

The exact RGB / 256-colour values are an implementation detail of
`styling.py` and may be tuned without amending this contract. The
pairwise distinguishability of `row.*` classes (US2.AC-1) and the
visibility of `pointer + highlighted` on every `row.*` background
(US3.AC-2) are the only invariants the contract guarantees.

---

## Cursor / focus indicator (FR-004)

The focused row MUST carry BOTH:

- A left-edge pointer glyph rendered by Questionary's `pointer` style
  class. When colour is enabled the default glyph is replaced with
  `▶ ` (a right-pointing triangle + trailing space). When colour is
  disabled, Questionary's built-in default (`» `) is used.
- A reverse-video text background driven by the `highlighted` style
  class.

When colour is disabled, the row text background is unchanged
(Questionary still draws the pointer glyph in front of the focused
choice, so US3.AC-1 — "exactly one row marked at all times" — still
holds in monochrome).

---

## Monochrome fallback (FR-007, SC-004)

When `styling.is_color_enabled()` returns `False`:

- Every `Choice.title` MUST be a plain `str` (no FormattedText
  tuples).
- The `style=` argument MUST be omitted from every Questionary call.
- The output (when captured by `pty`-less tests or piped to a file)
  MUST contain zero raw escape sequences — not even a stray
  `\x1b[0m`.
- The column layout MUST be preserved unchanged.

Triggers for monochrome:

1. `NO_COLOR` is set to a non-empty value.
2. `sys.stdout.isatty()` returns `False`.
3. `TERM == "dumb"`.

Otherwise colour is enabled.

---

## What the rendering contract does NOT promise

- **Specific RGB values**: the palette is allowed to be tuned for
  readability without amending this contract.
- **Per-user themes**: only a single palette ships in v1.
- **Terminal width adaptation**: rows are truncated at the right
  edge by Questionary when the terminal is narrower than the
  content. The `Day` / `Date` / `Hours` columns are designed to fit
  comfortably inside 80 columns; the `State` column may truncate on
  very narrow terminals (allowed by the spec's "truncate, but never
  corrupt navigation" rule).
- **Screen-reader semantics**: the table is plain text; screen
  readers will read each row left-to-right. No ARIA-equivalent
  metadata is emitted.
