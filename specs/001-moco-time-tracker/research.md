# Research: Moco Monthly Time Tracker CLI

**Feature**: 001-moco-time-tracker
**Date**: 2026-06-01

This document resolves every `NEEDS CLARIFICATION` item from the Technical
Context section of `plan.md`. Decisions here are inputs to `data-model.md`,
`contracts/`, and the upcoming `tasks.md`.

---

## 1. Moco API surface

**Decision**: Use the Moco REST API as documented at
`https://everii-group.github.io/mocoapp-api-docs/`. Base URL for this user:
`https://statista.mocoapp.com/api/v1`.

| Need | Endpoint | Notes |
|------|----------|-------|
| Authenticate every request | Header `Authorization: Token token=<API_KEY>` | Single header value; no refresh, no OAuth dance. |
| List projects the user can book against | `GET /projects/assigned` | Tasks are embedded under each project, so no second call is needed to populate task choices. Satisfies FR-003 and FR-004 with one round-trip. |
| Detect existing-hour totals per day (FR-012) | `GET /activities?from=YYYY-MM-01&to=YYYY-MM-LAST&user_id=<me>` | Filter on the chosen month and current user **across all projects and tasks** (clarification 2026-06-01). Returned rows are summed per `date`. Dates with a sum ≥ 8h become `already_logged=True` (locked, day full); dates with a sum > 0 but < 8h carry an auto-reduced default of `8 − existing_total` so submission tops the day up to 8h. |
| Bulk-create the month (FR-010) | `POST /activities/bulk` with body `{"activities": [ … ]}` | Confirmed in docs: a true bulk endpoint exists. Required per-row fields: `date`, `project_id`, `task_id`, `seconds`. We will also send `description` (constant — see §5) and `billable` (see §5). Per FR-011, the client parses the response for per-row status when Moco provides it; if the endpoint returns opaque atomic success/failure, every row inherits the overall outcome (see `data-model.md` `SubmissionResult` construction rule). |

**Rationale**: The spec says "single bulk request" — the Moco API provides
exactly that primitive, so no client-side batching loop is needed.

**Alternatives considered**:

- Looping `POST /activities` one-row-at-a-time. Rejected: FR-010 still requires
  a single bulk request. The clarification round on 2026-06-01 added per-row
  outcome reporting (FR-011), but per `data-model.md` `SubmissionResult` we
  satisfy that by parsing per-row data from the bulk response where Moco
  provides it and falling back to a unified outcome where it does not. This
  keeps the loop avoided while preserving partial-failure visibility.
- Using `/projects` (full list, all users) instead of `/projects/assigned`.
  Rejected: returns projects the user may not be allowed to book against,
  which makes the task-selection step misleading.

**Identifying the current user for the "already logged" filter**: Moco exposes
`GET /session` (current authenticated user info). On the first authenticated
call we will fetch this once and cache the `user_id` for the run.

---

## 2. Interactive preview table that supports arrow-key navigation + editing

**Decision**: Drive navigation, highlighting, and editing using `questionary`
primitives only — specifically `questionary.select` (which natively supports
arrow-key navigation and visually highlights the focused choice). The "preview
table" is rendered as a list of monospace-aligned choice lines; each line is
one date row.

Flow inside the preview:

1. The preview is a `select` whose choices are:
   - One choice per planned/already-logged row (formatted columns).
   - A separator.
   - `✅ Approve & submit`
   - `✏️  Edit a row` (re-enters the select after editing)
   - `❌ Cancel`
2. Selecting a data row opens a second `select` ("Skip this row" / "Include
   this row" / "Change hours" / "Back") whose options are conditional on the
   row's current state. Rows flagged `already_logged` only offer "Back"
   (enforces FR-012's no-toggle rule).
3. Editing hours uses `questionary.text` with input validation (non-negative
   decimal, ≤ 8 per FR-008 — clarification 2026-06-01).

**Rationale**:

- Constitution §I mandates Questionary for interactive prompts. A
  third-party TUI framework (Textual, urwid, prompt_toolkit raw) would
  bypass that mandate and add a heavy dependency for a one-screen workflow.
- `questionary.select` already gives keyboard-only navigation, visible
  highlight, and accept-on-enter, which is exactly what FR-007 and SC-005
  require.
- Rendering rows as fixed-width columns inside choice strings is enough to
  feel like a table without pulling in `rich` or `tabulate`.

**Alternatives considered**:

- `rich.table.Table` for rendering + a separate input prompt for selection.
  Rejected: adds a dependency for cosmetic gain, and `rich` tables aren't
  themselves interactive — we'd still need a separate prompt to capture the
  row index, which is exactly what `questionary.select` already gives us
  natively.
- `prompt_toolkit` directly. Rejected: heavier and would mean Questionary is
  used "only sometimes", violating §I.
- A custom curses-based table. Rejected: same dependency objection plus
  cross-terminal flakiness.

**Narrow-terminal behavior** (edge case in spec): row strings are built with
fixed minimum widths; if the terminal is narrower, Questionary truncates the
visible portion but the underlying choice list stays correct. Navigation
remains usable (acceptable per the spec's "truncate or wrap, but never
corrupt navigation").

---

## 3. Credential handling

**Decision**: Resolve the API key in this priority order, never persisting it
to disk:

1. Environment variable `MOCO_API_KEY` (power-user path, FR-001 second clause).
2. Interactive `questionary.password` prompt with masked input (FR-001 first
   clause).

The key lives only in a local variable that is passed to the HTTP client and
released when the process exits. We do not write it to any file the tool
creates. We do not log it. We do not place it in argv (so it cannot leak via
`ps`).

**Rationale**: This is the smallest design that satisfies FR-001, SC-004, and
User Story 2 — and `questionary.password` is the project-blessed primitive for
masked input.

**Alternatives considered**:

- Reading from a `~/.moco` dotfile. Rejected: spec says the user
  "explicitly does not want a checked-in key" *and* "kept only for the
  duration of the run". A home-directory dotfile would survive the run
  and gradually become a credential-management problem.
- A `--api-key` CLI flag. Rejected: would leak via shell history and `ps`.

---

## 4. Date/calendar computation

**Decision**: Use only the Python standard library (`datetime`, `calendar`)
to enumerate Mon–Fri dates of the chosen month. Default month is the current
month at process start (FR-002).

**Rationale**: Stdlib is sufficient, deterministic, and trivially unit-testable
— which matches §IV (unit tests mandatory) and the dependency-minimization
guidance in the constitution's Technology Stack section.

**Alternatives considered**: `pendulum`, `arrow`. Rejected: added dependency
for no behavior we need.

**Holiday handling**: explicitly out of scope per the spec's Assumptions — users
skip holidays manually in the preview. No holiday library is added.

---

## 5. Fixed description and billable flag for each row

**Decision**: All rows submitted in v1 share the same description string,
hard-coded as `"Administration"`, and `billable=false`. Per-row description
editing is out of scope (Assumptions in spec, and FR-008 explicitly excludes
it).

**Rationale**: The spec's Assumptions section calls out a single fixed
description as v1 behavior. Choosing `"Administration"` matches the
default task name and is the most informative no-input default.
`billable=false` reflects that "Administration" is internal time at the user's
organization; if this needs to flip, it becomes a one-line change.

**Alternatives considered**: Prompt for a description once at startup.
Rejected for v1: adds a step the spec did not request. Marked as a candidate
for a follow-up if users ask.

---

## 6. Error handling and exit codes

**Decision**: Map error categories to specific non-zero exit codes (FR-013):

| Category | Exit code | Behavior |
|----------|-----------|----------|
| Authentication failure (HTTP 401/403) | `2` | Print "Authentication failed: check your Moco API key." and stop before any selection UI. |
| No projects assigned | `3` | Print "No projects are assigned to your Moco account." |
| Chosen project has no tasks | `4` | Print "Selected project has no tasks." |
| Nothing left to submit (all rows skipped) | `5` | Print "No entries to submit; exiting without contacting Moco." (edge case in spec). |
| Bulk-submit total failure (no rows created) | `6` | Print "Bulk submission failed; no entries were created." (FR-011 atomic-failure branch). |
| Bulk-submit partial failure (some rows created, some failed) | `7` | Print "Created M of N entries for `<YYYY-MM>`. Failed: …" with the list of failed dates and reasons (FR-011 partial-failure branch, clarification 2026-06-01). |
| User cancels at preview | `0` | Clean exit per FR-009 + AS-1.4. |

**Rationale**: Distinct exit codes make the CLI scriptable later and make
test assertions explicit. Codes 2–6 are arbitrary but stable.

**Alternatives considered**: Single non-zero exit code for all errors.
Rejected: harder to test, harder to script around later.

---

## 7. HTTP client choice

**Decision**: Use the `requests` library for the Moco HTTP calls, with an
explicit per-call `timeout` (e.g., 15s) so a hanging network doesn't wedge the
preview.

**Rationale**: `requests` is the de-facto Python HTTP client, has no surprising
defaults, and is easy to stub in unit tests using the `responses` library.

**Alternatives considered**:

- `urllib.request` from stdlib. Rejected: too verbose for the four endpoints
  we call; less ergonomic to mock.
- `httpx`. Rejected: gains us async behavior we don't need (the CLI is
  inherently synchronous and interactive).

---

## 8. Unit-test boundary

**Decision**: Per constitution §IV, write unit tests for:

- Calendar/weekday enumeration (`calendar_utils`).
- Planner logic that merges weekday dates with the already-logged set,
  applies edits, and produces the final payload (`planner`).
- Moco client request shaping and response parsing, with HTTP mocked by
  `responses` (`moco_client`).
- Dataclass invariants (`models`).
- The pure logic functions extracted from `preview` (toggle, edit-hours,
  next-included-row, etc.) — but **not** the live Questionary loop itself,
  which is interactive UI.

No integration tests; no contract tests against the real Moco API.

**Rationale**: Mirrors §IV directly and keeps the test pyramid small for an
MVP that gates on visual approval anyway.

---

## Summary of resolved unknowns

| Spec area | Outcome |
|-----------|---------|
| Bulk submission endpoint | `POST /activities/bulk` (confirmed in Moco docs) |
| Auth header | `Authorization: Token token=<key>` |
| Project + task fetch | `GET /projects/assigned` (one round-trip; tasks embedded) |
| Already-logged detection | `GET /activities?from=&to=&user_id=` filtered to current user via `GET /session`; sum `hours` per date across all projects/tasks; ≥ 8h = locked, > 0 & < 8h = auto top-up to 8h (clarification 2026-06-01) |
| Table UX | `questionary.select` with row-shaped choice strings (no `rich`, no `prompt_toolkit`) |
| Credentials | env var `MOCO_API_KEY` → `questionary.password` fallback; never written to disk |
| Fixed description | `"Administration"`, `billable=false`, hard-coded in v1 |
| Date math | stdlib `datetime` + `calendar`, no extra dep |
| HTTP client | `requests` with explicit timeouts |
| Holiday handling | Out of scope; manual skip in preview |
