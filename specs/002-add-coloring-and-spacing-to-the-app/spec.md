# Feature Specification: Make moco-filler Preview Look Like a Table

**Feature Branch**: `002-add-coloring-and-spacing-to-the-app`

**Created**: 2026-06-01

**Status**: Draft

**Input**: User description: "make the moco-filler app more UX UI freindly make the days have more spaces and also coloring. Where it also shows where the cursor is. It should look like a table but in a terminal. Cool"

## Clarifications

### Session 2026-06-01

- Q: Should the new styling apply only to the preview, or also to the
  pickers and sub-menus? → A: Apply to the preview, both pickers
  (project + task), AND the per-row sub-menu — consistent visual
  identity across every interactive screen in one run.
- Q: Should the palette be chosen with explicit colour-blind safety in
  v1? → A: No — colour-blind safety is out of scope for this iteration.
  The multi-channel guarantee (state label + cursor glyph + colour)
  remains the fallback for users who can't distinguish two palette
  colours; a dedicated colour-blind-safe palette / opt-in theme may
  be revisited later but is not required now.

## User Scenarios & Testing *(mandatory)*

The user runs `moco-filler` interactively and reads the preview of a whole
month at a glance. Today every row is one undecorated, equally-weighted
line of plain text, the focused row is only subtly highlighted, and the
four row states (`planned` / `top-up` / `already logged` / `skipped`) are
distinguished only by a bracketed word at the end of the line. The user
has explicitly asked for the preview to feel like a table — with
breathing room between columns, a visible cursor marker, and color so
state is obvious without reading the label.

### User Story 1 - Read the month at a glance as a real table (Priority: P1) 🎯 MVP

The user opens the preview and immediately sees a **column-aligned
table** with a header row (e.g. `Day  Date         Hours   State`) and
enough horizontal whitespace between columns that the eye doesn't have
to hunt. Every date row lines up under the same column position so the
weekday, the date, the hours, and the state label all read like a
spreadsheet rather than a paragraph.

**Why this priority**: The whole reason for the feature exists is that
the current preview is hard to scan at a glance. Without the columnar
layout the other improvements (color, cursor) cannot anchor anywhere
visually. This is the MVP for the feature.

**Independent Test**: Run the CLI against an unfilled month. The preview
shows a header row whose columns align with every data row beneath it,
each column separated by clearly visible whitespace (at least two
spaces). Resize the terminal to 80 columns; the alignment still holds
(within the spec's existing "truncate, but never corrupt navigation"
allowance).

**Acceptance Scenarios**:

1. **Given** a month with 22 weekdays, **When** the preview opens,
   **Then** there is a header row above the data rows whose `Day`,
   `Date`, `Hours`, and `State` labels appear directly above the
   matching values in every data row.
2. **Given** any preview screen, **When** the user looks at column
   widths, **Then** the Date column is wide enough for `YYYY-MM-DD`
   without truncation, the Hours column is wide enough for `0.00h`
   through `8.00h`, and the State column starts at the same screen
   column for every row.
3. **Given** rows with different label lengths (`[planned]` vs
   `[top-up: existing 4.50h]` vs `[already logged]`), **When** the user
   scans down the column, **Then** all state labels start at the same
   screen column so the eye can follow a single vertical line.

---

### User Story 2 - See state at a glance via color (Priority: P2)

Each row's state is reinforced with a distinct color so the user can
spot already-logged days, partial days, and skipped days without
reading the trailing label.

**Why this priority**: Color triples the scan speed once the table
layout is in place, but it is layered visual reinforcement — the table
in US1 is still usable in black-and-white, so this story is P2 rather
than P1.

**Independent Test**: Open the preview on a month where one date is
already at 8h elsewhere, one date is a partial top-up, and the rest are
empty. Confirm the three states are visually distinct from the
unaffected `planned` rows when looking at the screen from across the
room (i.e. without reading any text).

**Acceptance Scenarios**:

1. **Given** the preview is open on a colour-capable terminal,
   **When** the user looks at the rows, **Then** each of `planned`,
   `top-up`, `already logged`, and `skipped` rows is rendered in a
   distinguishable color and these colors are consistent within one
   run.
2. **Given** the user toggles a row from `planned` to `skipped` and
   back, **When** the preview re-renders after each edit, **Then** the
   row's color updates to match its new state.
3. **Given** the user runs the CLI in an environment that does not
   support colour (e.g. a pipe, a CI log, or with `NO_COLOR` set per
   the cross-platform convention), **When** the preview is shown,
   **Then** the table still renders with correct alignment in plain
   monochrome and no raw escape sequences leak into the output.

---

### User Story 3 - Know exactly where the cursor is (Priority: P2)

The focused row is unmistakably the focused row: it carries a
left-edge marker (e.g. `▶`) AND a visually distinct color/background
so the user never has to squint to find their place.

**Why this priority**: Today the focused row is only modestly
highlighted by Questionary's default theme. After US1 lengthens rows
and US2 adds color, the cursor needs to win the visual contest, so it
sits at P2 alongside US2.

**Independent Test**: Open the preview and press the down-arrow a few
times. At every step exactly one row is marked as focused, that row
clearly differs from every other row, and pressing Enter on the marked
row opens the sub-menu for that exact row (no off-by-one).

**Acceptance Scenarios**:

1. **Given** the preview is open, **When** the user navigates with
   the arrow keys, **Then** the focused row carries a left-edge marker
   that is not present on any other row.
2. **Given** the user moves focus from a `planned` row to an
   `already logged` row, **When** the focus arrives on the locked
   row, **Then** the focus indicator is still clearly visible (the
   locked-row color does not visually overpower the cursor marker).
3. **Given** a terminal that doesn't render the chosen marker glyph,
   **When** the preview is shown, **Then** focus is still indicated
   by something fall-back (color/background) so the user is never
   left guessing which row is focused.

---

### Edge Cases

- The preview is shown on a narrow terminal (≤ 80 columns). The columns
  must remain aligned and the cursor marker visible; truncation at the
  right edge is acceptable per the existing "truncate or wrap, but
  never corrupt navigation" rule.
- The preview is shown on a non-colour terminal or with `NO_COLOR=1`.
  No raw escape sequences may leak; the table must still render
  cleanly in monochrome.
- A row's state label is unusually long (e.g.
  `[top-up: existing 7.75h]`). The State column must accommodate the
  longest possible label without breaking alignment of subsequent
  rows.
- The user pages between rows quickly. The cursor marker must never
  appear on two rows simultaneously between repaints.
- The preview is shown to a user using a screen reader. The visual
  cursor enhancement must not destroy the row text as readable plain
  text.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The preview MUST present rows as a left-aligned columnar
  table with a header row labelling each column (`Day`, `Date`,
  `Hours`, `State`).
- **FR-002**: Every data row's columns MUST start at the same screen
  column position so the table reads vertically.
- **FR-003**: The columns MUST be separated by visible whitespace (at
  least two spaces per gap) so individual values are not visually
  collided.
- **FR-004**: The currently-focused row MUST be visually distinct from
  every other row via BOTH a left-edge marker character AND a colour
  or background change.
- **FR-005**: Each of the four row states (`planned`, `top-up`,
  `already logged`, `skipped`) MUST be rendered in its own
  consistent color when the terminal supports colour.
- **FR-006**: The visual treatment of the four actions
  (`Approve & submit`, `Cancel`, `Back`, `Change hours`) MUST be
  visually distinct from data rows, and `Approve & submit` and
  `Cancel` MUST be visually distinguishable from each other (so a
  user cannot mistake Cancel for Approve in a hurry).
- **FR-007**: When the terminal does not support colour or
  `NO_COLOR` is set in the environment per the cross-platform
  convention, the preview MUST fall back to plain monochrome with
  zero raw escape sequences in the output and the columnar layout
  preserved.
- **FR-008**: The visual changes MUST NOT change the functional
  behaviour of the preview — every action available before this
  feature (navigate, approve, cancel, skip, include, change hours,
  back) MUST remain available and produce the same outcome.
- **FR-008a**: The visual treatment (palette + cursor marker + chrome
  styling) MUST be applied consistently across every interactive
  screen in one CLI run: the project picker, the task picker, the
  preview, and the per-row sub-menu (`Skip` / `Include` / `Change
  hours` / `Back`). No screen reverts to Questionary's default,
  unstyled appearance.
- **FR-009**: The visual changes MUST NOT introduce a new
  user-visible dependency beyond what the project already ships with;
  the existing Questionary-only mandate for interactive prompts
  remains in force.
- **FR-010**: The columnar layout MUST hold for every month length
  (28 / 29 / 30 / 31 days) and every state combination.

### Key Entities

This feature does not introduce new domain entities. It changes how
existing `PlannedEntry` rows are rendered. The only new concept is a
**Row presentation** — a derived view of an existing `PlannedEntry`
made up of: column-aligned cells, a state-derived colour token, and a
focus marker that is present on exactly one row at a time.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user shown the preview for the first time can
  correctly identify which row is currently focused in under 1
  second without being told.
- **SC-002**: A new user can correctly identify the state of any
  given row (planned / top-up / already logged / skipped) in under 2
  seconds without reading the trailing label.
- **SC-003**: In a colour-capable terminal at any width ≥ 80
  columns, every data row's four columns align vertically with the
  header (zero rows out of alignment).
- **SC-004**: In a non-colour environment (pipe, CI log, or
  `NO_COLOR=1`), the preview output contains zero raw escape
  sequences and the column alignment is preserved.
- **SC-005**: The change does not increase the runtime of a happy-path
  `moco-filler --month YYYY-MM` run by more than 100ms versus the
  prior implementation (i.e. styling is effectively free at
  human-interactive scale).
- **SC-006**: 100% of pre-existing automated tests continue to pass
  after the change — no behavioural regression.

## Assumptions

- The project's Questionary-only mandate (Constitution §I) remains in
  force; no replacement TUI library (e.g. `rich`, `textual`,
  `prompt_toolkit` used directly, `curses`) is introduced. The
  feature uses only what Questionary already exposes (e.g. its
  `style` parameter via the prompt_toolkit `Style` dictionary it
  already accepts) and plain ANSI escape sequences where Questionary
  doesn't cover the gap.
- "Colour-capable terminal" means an attached TTY that does not
  explicitly opt out via the cross-platform `NO_COLOR` convention.
  When stdout is not a TTY the CLI falls back to monochrome
  automatically.
- The colour palette is left to the implementer; the spec only
  requires that the four states are pairwise distinguishable and that
  the focus marker is visible on every state's row.
- Per-row description editing, an "edit any row inline" mode, search
  / filter, and configurable colour themes are explicitly out of
  scope for v1 of this feature. Configurable themes may be added
  later but are not required.
- **Colour-blind-safe palette is explicitly OUT OF SCOPE for v1**
  (confirmed in the 2026-06-01 clarification session). The palette
  may use red and green; users for whom colour alone is unreliable
  rely on the state label and the cursor glyph, both of which remain
  present in colour mode. A dedicated colour-blind-safe theme is a
  candidate for a follow-up feature, not v1.
- This feature touches only the interactive preview and the
  surrounding pickers / sub-menus that share its visual language. The
  underlying domain models (`PlannedEntry`, `SubmissionBatch`, etc.),
  the HTTP client, and the existing exit codes are unchanged.
- The CLI's stdout contract (the five exact lines documented in
  `specs/001-create-mvp-moco-filler-app/contracts/cli.md` § stdout / stderr
  contract) is not changed by this feature, so any external tooling
  that scrapes those lines keeps working.
