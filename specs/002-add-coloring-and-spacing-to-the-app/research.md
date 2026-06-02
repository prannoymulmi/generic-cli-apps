# Research: Table-Styled Preview for moco-filler

**Feature**: 002-add-coloring-and-spacing-to-the-app

**Date**: 2026-06-01

This document resolves every `NEEDS CLARIFICATION` item from the
Technical Context section of `plan.md`. Decisions here feed
`data-model.md`, `contracts/preview-rendering.md`, and the upcoming
`tasks.md`.

---

## 1. How to draw a column-aligned table inside `questionary.select`

**Decision**: Render each row as a fixed-width-column string built with
Python's f-string format specifiers (e.g.
`f"{day:<3}  {date:<10}  {hours:>5}  {label}"`) and hand it to
Questionary as part of a `Choice` whose title is a list of
prompt_toolkit FormattedText `(style_class, text)` tuples. A
`questionary.Separator` placed at the top of the choice list acts as a
non-selectable **header row** carrying the same column layout so the
data rows visually anchor under it.

**Rationale**:

- Questionary's `Choice.title` accepts both `str` and the prompt_toolkit
  FormattedText shape `list[tuple[str, str]]`. The tuple shape lets us
  attach style classes per fragment without injecting raw ANSI codes
  (which prompt_toolkit would escape).
- `Separator` is the documented way to put non-selectable lines into a
  `select` list, which is exactly the role of a header row.
- Fixed-width column padding is two lines of pure Python and gives us
  exact control over the alignment that FR-002 / FR-003 require.

**Alternatives considered**:

- A second prompt before the `select` printing the header via `print()`.
  Rejected: the header would scroll out of view as Questionary repaints
  the choice list during navigation, defeating FR-001.
- `rich.table.Table` inside the choice strings. Rejected: introduces a
  new top-level dependency for cosmetic gain, violates the Constitution
  §I Questionary-only mandate, and would also be re-escaped by
  prompt_toolkit.
- Embedding raw ANSI escape sequences in plain-string titles. Rejected:
  prompt_toolkit treats title strings as plain text and escapes / drops
  unknown control bytes, so the colours wouldn't apply consistently.

---

## 2. Where the colour palette lives and how it is applied

**Decision**: Build a single prompt_toolkit `Style.from_dict` mapping
inside a new `styling.py` module's `build_style()` factory, exposing
named style classes that match the row states and the chrome:

| Style class | Used by | Default colour |
|-------------|---------|----------------|
| `row.planned` | a plain weekday row | cyan / default fg |
| `row.topup` | a partial-day row | yellow |
| `row.locked` | an already-logged row | dim grey |
| `row.skipped` | a user-skipped row | dim red strikethrough-feel |
| `row.header` | the header `Separator` row | bold underline |
| `pointer` | Questionary chrome — the cursor symbol | bright green bold |
| `highlighted` | Questionary chrome — focused row | reverse video |
| `qmark` | Questionary chrome — leading `?` | bright green bold |
| `instruction` | Questionary chrome — keybinding hint | dim |
| `selected` | Questionary chrome — picked choice | bright green |
| `separator` | Questionary chrome — separator line | grey |
| `action.approve` | the `Approve & submit` choice | bright green bold |
| `action.cancel` | the `Cancel` choice | bright red bold |

`build_style()` returns the assembled `Style` plus a sentinel `None`
when colour is disabled. Choice titles are constructed as
FormattedText tuples like `[("class:row.topup", "Wed 2026-06-03   3.50h   [top-up: existing 4.50h]")]`.

**Rationale**:

- A `Style.from_dict` is the documented Questionary path for theming
  and is what its docs recommend for projects that want consistent
  pointer / highlight / qmark colours.
- Using *classes* (not raw colour strings) inside `Choice.title`
  keeps every colour decision in one file — adjusting the palette
  later requires no `preview.py` edits.
- The class names are namespaced (`row.*`, `action.*`) so they read
  at the call site without comments.

**Alternatives considered**:

- One colour per row, hard-coded inside `preview.py`. Rejected: spreads
  presentation logic across files, complicates a future theme switch,
  and pulls colour decisions out of `styling.py`'s single
  responsibility.
- Reusing the `colorama` library. Rejected: redundant — prompt_toolkit
  already handles cross-platform ANSI translation, and `colorama` would
  fight for the same stdout fd.

---

## 3. Detecting when to render in monochrome

**Decision**: `styling.is_color_enabled()` returns `False` when ANY of
the following hold:

1. The `NO_COLOR` environment variable is set to a non-empty value
   (per the cross-platform `https://no-color.org/` convention).
2. `sys.stdout.isatty()` is `False` (output is being piped or
   redirected).
3. The `TERM` environment variable equals `"dumb"`.

Otherwise it returns `True`. When colour is disabled, `build_style()`
returns `None`; the row-formatter falls back to plain `str` titles, and
the `Style` argument to every `questionary.select` call is omitted.

**Rationale**:

- `NO_COLOR=1` is the industry standard the spec already cites
  (FR-007).
- The TTY check covers CI / pipe / `tee` cases the user can't
  reasonably annotate by hand.
- `TERM=dumb` is the canonical "very-old or stripped terminal" signal
  GNU-style tools honour.

**Alternatives considered**:

- A `--no-color` CLI flag. Rejected: the env var already covers it and
  the CLI today accepts only `--month` (`contracts/cli.md` § Invocation
  is intentionally tiny).
- Always rendering colour. Rejected: violates FR-007 and produces raw
  escape sequences in CI logs and pipes.

---

## 4. How the focused row stays unambiguously visible

**Decision**: Use two reinforcing signals on the focused row, both
driven by the prompt_toolkit `Style.from_dict` so they survive any
single-channel failure (e.g. a screen reader that strips colour but
keeps glyphs, or a colour-blind user):

1. **Left-edge marker glyph** — set Questionary's `pointer` chrome to
   `▶ ` with `pointer = "fg:#00ff00 bold"`. Questionary renders this
   to the immediate left of the focused choice and nowhere else, so the
   "exactly one pointer at a time" rule from FR-004 / US3.AC-1 is
   guaranteed by Questionary itself.
2. **Background contrast on the row text** — set `highlighted =
   "reverse"` so the focused choice gets a reversed-video background.
   `reverse` works in every ANSI-capable terminal and degrades
   gracefully on terminals that lack 256-colour support (US3.AC-2,
   AC-3).

When colour is disabled, Questionary still renders its default pointer
glyph (a leading `»`) which keeps the focus visible — i.e. the
no-colour path still satisfies FR-004's "at least one indicator"
requirement.

**Rationale**:

- The pointer and the background are *independent* visual channels, so
  losing one still leaves the other.
- `reverse` is the most-portable way to mark a focused row across
  ANSI-capable terminals (works the same on Terminal.app, iTerm2,
  Alacritty, GNOME Terminal, plus tmux and screen).

**Alternatives considered**:

- A multi-byte block character (`█`) as the pointer. Rejected: doesn't
  render on every terminal font; the spec's US3.AC-3 explicitly calls
  out the missing-glyph fallback case.
- Underline-only highlight. Rejected: weak signal next to coloured
  state labels; would frequently fail SC-001 ("identify focused row in
  under 1 second").

---

## 5. Column widths and the header row

**Decision**: Use these fixed minimum widths, calculated from the
longest possible content in each column:

| Column | Width | Worst-case content |
|--------|-------|--------------------|
| Day | 3 chars | `Wed`, `Thu`, `Fri` — `strftime("%a")` is exactly 3 chars in en_US |
| Date | 10 chars | `YYYY-MM-DD` is always exactly 10 chars |
| Hours | 5 chars | `8.00h` — the rendered `f"{hours:.2f}h"` fits in 5 chars across `[0, 8]` |
| State | flexible | longest is `[top-up: existing 7.75h]` (24 chars) — left-aligned, no trailing padding |

Gaps between columns: **two spaces** (FR-003). The header row uses the
same widths and gap, with column labels `Day`, `Date`, `Hours`, `State`.
A `questionary.Separator` printed with the assembled header string is
inserted as the first choice in the list (above all data rows) so it
visually anchors the columns.

**Rationale**: The widths are determined entirely by data the planner
already produces — no measurement loop, no terminal-size queries
required. This matches the planner's deterministic output (FR-010 —
"any month length").

**Alternatives considered**:

- Dynamic column widths computed from the actual rendered rows.
  Rejected: adds a precomputation pass that buys nothing because the
  longest content is known statically.
- Right-aligning the Day column. Rejected: `Mon`/`Tue`/`Wed`/`Thu`/`Fri`
  are all 3 chars in en_US so alignment is a no-op; left-alignment
  reads more naturally next to the date.

---

## 6. Where the styling module fits with the existing modules

**Decision**: A new `src/moco_filler/styling.py` owns:

1. `build_style() -> Optional[Style]` — assembles the
   `Style.from_dict`, returns `None` when colour is disabled.
2. `is_color_enabled() -> bool` — the predicate from §3.
3. `format_row(entry: PlannedEntry, *, color: bool) -> str | list[tuple[str, str]]` —
   returns a FormattedText list when colour is on, a plain `str` when
   colour is off. (Returning two shapes is fine because Questionary's
   `Choice.title` already accepts both.)
4. `format_header() -> str | list[tuple[str, str]]` — the matching
   header row for the leading `Separator`.
5. `format_action(label: str, kind: Literal["approve", "cancel"]) -> str | list[tuple[str, str]]` —
   the styled choice titles for the Approve / Cancel actions.

`preview.py` imports these and the existing `running_total` /
`next_included_row` / `state_label` helpers stay where they are. `cli.py`
imports `build_style()` once at startup and passes the resulting
`Style` to the project picker, the task picker, and `show_preview()`.

**Rationale**: Keeps presentation policy in exactly one file
(Constitution §V). `preview.py`'s read-the-spec-aloud orchestration
shape (defined in feature 001) stays intact.

**Alternatives considered**:

- Inlining the palette into `preview.py`. Rejected: same-file styling
  cross-cuts `cli.py`'s pickers, so a single source-of-truth file is
  more maintainable.
- A `themes/` subpackage. Rejected: one palette in v1 doesn't justify
  a package; revisit if multiple themes are added later.

---

## 7. Backwards-compat with existing tests

**Decision**: The existing `tests/test_preview_logic.py` asserts the
*plain-string* output of `format_row(entry)` (one positional arg). Two
options:

- **(a)** Keep the existing signature for `format_row(entry)` — defined
  in `preview.py` — and have it return the plain string. Add a new
  `format_styled_row(entry)` (in `styling.py`) that returns the
  FormattedText list. `preview.py`'s `_build_choices` chooses one or
  the other based on the colour predicate.
- **(b)** Change `format_row` to accept a `color: bool` kwarg, return
  the styled list when `color=True`, the plain string otherwise. Update
  the existing tests to pass `color=False` explicitly.

Choose **(a)**. It avoids retesting every existing call site and keeps
the "pure helper" footprint that feature 001 deliberately exposed.

**Rationale**: Constitution §IV asks for test coverage; option (a)
leaves the existing assertions intact (zero regression) and the new
helper has its own dedicated test file.

---

## 8. Unit-test boundary for this feature

**Decision**: Per Constitution §IV, write unit tests for:

- `is_color_enabled()` across the four trigger combinations (no env, `NO_COLOR=1`, non-TTY, `TERM=dumb`).
- `build_style()` returning `None` when colour disabled, a `Style` instance otherwise.
- `format_styled_row()` returning the correct FormattedText tuple shape for each of the four states (plain / top-up / locked / skipped).
- `format_header()` returning a string whose column anchors match `format_row()`'s column positions.
- `format_action()` returning `action.approve` vs `action.cancel` style classes.

NOT tested: the live Questionary loop, the actual terminal rendering, and the visual fidelity of the colour choices (those are gated by US1–US3's Independent Test sections, which are sandbox / manual checks).

**Rationale**: Mirrors the same boundary feature 001 chose
(`specs/001-create-mvp-moco-filler-app/research.md` §8) — keep the test pyramid
small and the visual fidelity gated by manual review.

---

## Summary of resolved unknowns

| Question | Outcome |
|----------|---------|
| How to align columns inside `questionary.select` | Fixed-width f-string padding + a header `Separator` |
| Where colour comes from | `Style.from_dict` in a new `styling.py`; FormattedText tuples per row |
| When to drop colour | `NO_COLOR=1` OR non-TTY OR `TERM=dumb` |
| How to mark the focused row | Custom `pointer` glyph (`▶`) + `reverse` highlight, both via the Style |
| Column widths | Day=3, Date=10, Hours=5, State=flex; 2-space gaps |
| New module placement | Single new `src/moco_filler/styling.py` |
| New dependencies | None — only Questionary symbols already shipped |
| Existing-test compatibility | Keep `preview.format_row` plain; add `styling.format_styled_row` |
