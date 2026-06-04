# Feature Specification: Skip Hamburg Public Holidays in moco-filler

**Feature Branch**: `003-hamburg-holidays-skip`

**Created**: 2026-06-04

**Status**: Draft

**Input**: User description: "I want to now also take into consideration the holidays in hamburg and skip those days. However it should show it as holiday in the preview for the moco filler."

## User Scenarios & Testing *(mandatory)*

The user runs `moco-filler` interactively for a German calendar month
that contains one or more Hamburg public holidays (e.g., May 2026, which
contains *Tag der Arbeit* on the 1st and *Christi Himmelfahrt* on the
14th). Today every Mon–Fri is treated identically — the planner
defaults all weekdays to 8h and the preview only differentiates rows by
existing-hours state. The user has explicitly asked that Hamburg public
holidays be auto-skipped from the submission **and** be visibly marked
as holidays in the preview so they understand *why* a given weekday
was left out.

### User Story 1 — Hamburg holidays are auto-skipped from the plan (Priority: P1) 🎯 MVP

When the planner builds the month, any weekday that falls on a Hamburg
public holiday is created in a not-included state (hours = 0, excluded
from the eventual bulk submission), so the user never accidentally
books work hours on a public holiday.

**Why this priority**: The whole point of the feature is to stop the
user from accidentally submitting hours on a day they were legally not
working. Without this behaviour the rest of the feature (holiday
labelling in the preview) is just cosmetic.

**Independent Test**: Run the CLI for May 2026 against an unfilled
month. Without the user touching any row, confirm that the rows for
2026-05-01 (Tag der Arbeit) and 2026-05-14 (Christi Himmelfahrt) are
excluded from the would-be submission batch, while every other weekday
in May is included at the normal 8h default.

**Acceptance Scenarios**:

1. **Given** a month that contains at least one Hamburg public holiday
   on a weekday, **When** the user opens the preview without changing
   anything, **Then** every holiday weekday is in a not-included state
   with hours = 0 and would not be sent to the bulk endpoint if the
   user pressed Approve immediately.
2. **Given** a Hamburg holiday that falls on a Saturday or Sunday,
   **When** the preview is built, **Then** no row exists for that
   date (weekend rule unchanged from feature 001 FR-005) and no error
   or warning is raised.
3. **Given** a month containing zero Hamburg public holidays on
   weekdays (e.g., February in most years), **When** the preview opens,
   **Then** the preview is indistinguishable from the pre-feature
   behaviour for that month — every weekday is `planned` at 8h.

---

### User Story 2 — Holiday rows are visibly labelled in the preview (Priority: P1) 🎯 MVP

The preview shows holiday rows in a distinct, recognisable state that
names the holiday so the user can tell at a glance *why* the day was
skipped. A holiday row is not just a "skipped" row — it carries the
holiday's German name (e.g., `Karfreitag`, `Tag der Arbeit`, `Christi
Himmelfahrt`) in the row's State column so the user understands the
reason without needing to remember the calendar.

**Why this priority**: Skipping holidays silently would make the user
distrust the tool ("why did it drop that day?"). The label is what
turns the skip from a black-box decision into a transparent one. P1
because the user explicitly asked for it in the same request as the
skip behaviour.

**Independent Test**: Run the CLI for a month containing at least one
known Hamburg holiday. Confirm that the holiday's row visually
differs from a normal `skipped` row, that it shows the holiday's
German name, and that the row is recognisably "holiday" rather than
"user manually skipped".

**Acceptance Scenarios**:

1. **Given** a weekday that is a Hamburg public holiday, **When** the
   preview is rendered, **Then** the row's State column shows a
   holiday indicator that includes the holiday's German name (e.g.,
   `holiday: Karfreitag`).
2. **Given** the user toggles a normal weekday to `skipped` and a
   different weekday is auto-skipped because it is a holiday, **When**
   the user scans the preview, **Then** the two rows are visually and
   textually distinguishable — the holiday row says it is a holiday
   and names the holiday; the user-skipped row does not.
3. **Given** the preview is rendered in a colour-capable terminal,
   **When** the user looks at the holiday row, **Then** it is rendered
   in a colour distinct from the four pre-existing states (`planned`,
   `top-up`, `already logged`, `skipped`); in a non-colour
   environment, the holiday row still carries the textual `holiday: …`
   label so the information is never lost.

---

### User Story 3 — Override an auto-skipped holiday for the rare case (Priority: P3)

A user who actually did work on a public holiday can still book hours
on that day. The per-row sub-menu (the same one used for normal
`Skip` / `Include` / `Change hours` edits today) accepts overrides on
a holiday row, but the override must be a deliberate action — the
default state remains skipped.

**Why this priority**: 95%+ of users will never override a holiday.
This story exists so the tool isn't *more* restrictive than the
existing skipped-row behaviour, not because override is a primary
flow. P3 because the MVP (US1 + US2) is already useful without it.

**Independent Test**: On a month containing a holiday, open the
sub-menu for the holiday row, choose `Include` (and optionally
`Change hours`), confirm the row turns into a submitable entry, and
confirm the row's State column updates so it no longer claims to be a
"holiday skip" — the user has taken responsibility for that day.

**Acceptance Scenarios**:

1. **Given** a holiday row in the preview, **When** the user opens the
   sub-menu and selects `Include`, **Then** the row becomes
   submitable at the same default hours as any other re-included row
   and the holiday label is replaced with the normal included-row
   label (the holiday name is no longer shown as the reason the row
   is excluded, because it is no longer excluded).
2. **Given** the user has re-included a holiday row but then changes
   their mind, **When** the user selects `Skip` on the same row,
   **Then** the row returns to the holiday state (auto-skipped,
   holiday name visible) — i.e., the holiday-skip is the canonical
   "this is skipped" reason for that date, not an arbitrary user
   skip.

---

### Edge Cases

- **Movable feasts**: Hamburg observes several holidays whose date
  depends on Easter (Karfreitag, Ostermontag, Christi Himmelfahrt,
  Pfingstmontag). The system must compute the correct date for the
  chosen year — a static "list of dates from 2025" will silently drift
  in 2026, 2027, etc.
- **Holiday that coincides with already-logged hours**: if the user
  has already booked hours in Moco on a public holiday (rare but
  possible — they worked overtime), the row's `already logged` state
  takes precedence over the holiday state. The user already knows
  they worked; the tool must not overwrite that fact.
- **Holiday on a weekend**: no row exists (weekends are not in the
  preview at all), so there is nothing to label and nothing to skip.
  This is not an error.
- **A year outside the supported range**: if the user picks a month
  whose year is outside the holiday calendar's known range, the tool
  must not crash. It should treat the unknown year as having no
  holidays (i.e., behave as before this feature) and continue.
- **Reformationstag (31 October)**: Hamburg added this as a permanent
  public holiday in 2018. Months before 2018 must NOT mark 31 October
  as a holiday; 2018-onwards months MUST.
- **A future Hamburg-only or federal change to the holiday list**:
  the spec is silent on automatic updates — when the German holiday
  law changes, the holiday catalogue inside the tool must be updated
  by a follow-up release. There is no live "fetch from a government
  service" requirement in v1.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST recognise the official Hamburg public
  holidays applicable on each Mon-Fri date of the month under
  preview. The catalogue MUST include, at minimum: Neujahr, Karfreitag,
  Ostermontag, Tag der Arbeit, Christi Himmelfahrt, Pfingstmontag,
  Tag der Deutschen Einheit, Reformationstag (2018-onwards),
  Weihnachten (1. Weihnachtsfeiertag), and 2. Weihnachtsfeiertag.
- **FR-002**: When a weekday in the preview falls on a Hamburg public
  holiday, the planner MUST create that row in a not-included state
  with hours = 0 by default, so the row is excluded from the
  submission batch if the user approves without further edits.
- **FR-003**: The preview MUST render a holiday row in a state that
  is visually and textually distinct from the four pre-existing row
  states (`planned`, `top-up`, `already logged`, `skipped`).
- **FR-004**: The holiday row's State column MUST display the
  holiday's German name (e.g., `Karfreitag`) so the user knows
  *which* holiday is the reason the day was skipped.
- **FR-005**: When a date is both a Hamburg public holiday AND has
  pre-existing logged hours that already meet the day-full threshold,
  the row MUST be rendered in the `already logged` state, not the
  holiday state — the user already booked time, so the "skipped
  because holiday" reason no longer applies. The holiday status MAY
  still be surfaced as supplementary information but MUST NOT replace
  the already-logged signal.
- **FR-006**: A user MUST be able to override the auto-skip on a
  holiday row through the existing per-row sub-menu (`Include` /
  `Change hours`), turning the row into a normal submitable entry.
  Once overridden, the row MUST no longer be labelled as a holiday
  skip (because it is no longer skipped).
- **FR-007**: When a user explicitly `Skip`s a holiday row that they
  had previously re-included, the row MUST return to its canonical
  holiday-skipped state (holiday name visible, not-included, hours =
  0), not become a generic user-initiated skip.
- **FR-008**: The visual treatment of the holiday state MUST honour
  the colour-fallback rule from feature 002: in a non-colour
  environment (`NO_COLOR`, non-TTY, or unsupported terminal), the
  holiday label MUST still be readable in plain monochrome with no
  raw escape sequences in the output.
- **FR-009**: The change MUST NOT alter the stdout contract from
  `specs/001-create-mvp-moco-filler-app/contracts/cli.md` § stdout /
  stderr contract. The summary lines, error rendering, and exit codes
  remain identical.
- **FR-010**: The change MUST NOT introduce a new top-level
  user-visible dependency beyond what the project already ships with;
  any holiday catalogue MUST come from the standard library, a
  pinned bundled data table, or a single new pinned dependency
  decided in the implementation plan — NOT from a runtime network
  fetch.
- **FR-011**: The system MUST correctly compute movable feasts
  (Karfreitag, Ostermontag, Christi Himmelfahrt, Pfingstmontag) for
  the chosen calendar year, not rely on a static list of dates.
- **FR-012**: Holidays before 2018-10-31 MUST NOT include
  Reformationstag (the law making it a Hamburg public holiday was
  passed in 2018 and applies from that year forward). Holidays in
  2018-10-31 and onwards MUST include Reformationstag.
- **FR-013**: If the user selects a month whose year is outside the
  range supported by the holiday catalogue, the tool MUST behave
  exactly as before this feature for that month (no rows marked
  holiday, no error raised) — degradation is silent and non-fatal.

### Key Entities

This feature introduces one derived concept and lightly extends one
existing one:

- **Hamburg public holiday**: a (calendar date, German holiday name)
  pair valid for a given year. The date is computed (movable feasts)
  or fixed (Neujahr, Tag der Arbeit, Tag der Deutschen Einheit,
  Reformationstag from 2018, 1. and 2. Weihnachtsfeiertag) per the
  Hamburg law in force in that year.
- **PlannedEntry (extended)**: gains a holiday-skip reason. A
  PlannedEntry that exists today already carries the date, weekday,
  hours, included flag, already-logged flag, and an optional note;
  this feature adds a way to say "this row is excluded because the
  date is a Hamburg public holiday named X" so the preview and the
  per-row sub-menu can render and edit accordingly. No persistence
  changes — this state still lives only for the duration of one CLI
  run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any chosen month between January 2018 and December
  2030, every Hamburg public holiday that falls on a Mon-Fri is
  pre-marked as not-included in the preview without the user having
  to touch the row.
- **SC-002**: For the same range, every holiday-skipped row shows the
  correct German holiday name (e.g., `Christi Himmelfahrt`, not just
  `holiday`). 100% of holiday rows are correctly named.
- **SC-003**: A user shown a month with at least one holiday can
  identify, in under 3 seconds, which row was skipped because of a
  holiday vs. which row was skipped by their own earlier action — by
  visual and/or textual cue alone, without reading the description
  field.
- **SC-004**: Approving a month without manually editing any row
  results in a submission batch whose dates contain zero Hamburg
  public holidays — i.e., the auto-skip is correct end-to-end (not
  just visual in the preview).
- **SC-005**: When the user runs the CLI in a non-colour environment
  (`NO_COLOR=1`, piped stdout, or non-TTY), the preview output
  contains zero raw escape sequences and the holiday rows are still
  textually identifiable as holidays.
- **SC-006**: 100% of pre-existing automated tests from features 001
  and 002 continue to pass after this feature is implemented — no
  behavioural regression in the planner, the HTTP client, the
  preview wiring, or the styling.
- **SC-007**: The change adds no more than 100ms to the runtime of a
  happy-path `moco-filler --month YYYY-MM` invocation versus the
  pre-feature behaviour, on a month containing zero or many
  holidays.

## Assumptions

- "Hamburg public holiday" means a day that the Free and Hanseatic
  City of Hamburg recognises as a statutory public holiday
  (gesetzlicher Feiertag) in the law in force at that time. Other
  states' holidays (e.g., Allerheiligen, Heilige Drei Könige) are
  explicitly out of scope — they do not appear in the catalogue and
  do not influence the preview, even if the user is physically
  working in another state.
- The user's intent is the **Hamburg** holiday calendar specifically,
  not "Germany-wide" or "the user's billing-region calendar". A
  future feature could make the region configurable; v1 is
  Hamburg-only.
- The holiday catalogue lives in the tool itself (computed for
  movable feasts, hard-coded with documented dates for fixed ones).
  No network call is made to look up holidays — the tool remains
  offline-capable in the same way it is today (only the Moco API
  itself requires connectivity).
- The visual treatment of the new holiday state slots into the
  palette / cursor / chrome conventions already established by
  feature 002 (`specs/002-add-coloring-and-spacing-to-the-app`). The
  styling module gains one new state colour token; no other styling
  conventions change.
- The Questionary-only mandate (Constitution §I) and the existing
  exit-code contract remain in force. The HTTP client, the auth
  flow, the bulk-submission rules, and the stdout/stderr contract
  are not touched by this feature.
- Half-day holidays (Heiligabend 24. Dezember and Silvester 31.
  Dezember are NOT statutory holidays in Hamburg — they are at most
  shortened working days handled by individual employers) are NOT
  in scope. The tool treats them as normal weekdays. If the user's
  employer treats them differently, they can still `Skip` or
  `Change hours` per the existing per-row sub-menu.
- Calendar-year support of 2018 → 2030 is sufficient for v1; outside
  this range the tool degrades silently to the pre-feature behaviour
  per FR-013. Extending the range later is a configuration / data
  change, not a re-architecture.
