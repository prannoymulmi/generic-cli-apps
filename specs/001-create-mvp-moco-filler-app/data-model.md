# Data Model: Moco Monthly Time Tracker CLI

**Feature**: 001-create-mvp-moco-filler-app
**Date**: 2026-06-01

All entities live in memory only — nothing is persisted by this tool.
Types are Python `dataclasses` unless noted.

---

## `ApiCredentials`

Represents the in-memory API key for the current run.

| Field | Type | Notes |
|-------|------|-------|
| `token` | `str` | The Moco personal API key. |
| `source` | `Literal["env", "prompt"]` | Where it was supplied (for an audit log line, not for storage). |

**Lifetime**: created once at startup, passed by reference to the HTTP client,
discarded when the process exits.

**Validation**:

- `token` must be non-empty after trimming whitespace.
- The first authenticated call (`GET /session`) verifies the token; a 401/403
  causes exit code `2` (see research.md §6).

**Never**: written to disk, logged, or placed in `argv`.

---

## `Project`

Mirrors the relevant fields of a Moco project returned by
`GET /projects/assigned`.

| Field | Type | Notes |
|-------|------|-------|
| `id` | `int` | Moco's primary key. |
| `name` | `str` | Display name shown in the picker. |
| `tasks` | `list[Task]` | Embedded under the project in the same response. |

**Validation**:

- `tasks` may be empty; an empty list triggers exit code `4` if the user
  selects this project.

---

## `Task`

A task (service) inside a project.

| Field | Type | Notes |
|-------|------|-------|
| `id` | `int` | Moco's primary key for the task. |
| `name` | `str` | Display name. The picker defaults to a task named exactly `"Administration"` (case-sensitive) when present (FR-004). |

---

## `PlannedEntry`

One row of the preview table.

| Field | Type | Notes |
|-------|------|-------|
| `date` | `datetime.date` | A Mon–Fri date in the chosen month. |
| `weekday` | `str` | Short weekday name (e.g., `"Mon"`), computed from `date`. |
| `existing_hours_total` | `Decimal` | Sum of the user's existing time entries on `date` across **all projects and tasks** (FR-012). `Decimal("0")` when none. |
| `hours` | `Decimal` | Planned hours for this row. Default = `max(Decimal("0"), Decimal("8") − existing_hours_total)` so the day tops up to 8h (FR-005, FR-012). Editable to any value in `[0, 8]` (FR-008). Setting to `0` flips `included` to `False` (FR-008). |
| `included` | `bool` | `True` by default. Flipping to `False` excludes the row from the submission. Forced to `False` when `hours == 0`. |
| `already_logged` | `bool` | `True` when `existing_hours_total ≥ 8` ("day full" — FR-012). When `True`, the row is locked and excluded from the submission; users cannot toggle it back. |
| `note` | `str \| None` | Optional one-liner explaining why a row is in its current state — e.g., `"Already logged (day full)"` or `"Top-up: existing 4.50h"`. Display-only; not sent to Moco. |

**Derived properties** (not fields):

- `is_submitable`: `included and hours > 0 and not already_logged`.
- `seconds`: `int(hours * 3600)`. Used to populate the `seconds` field that
  Moco's bulk endpoint requires.

**State transitions** (driven by the preview UI):

```
                  ┌──────────────────────────────────────┐
                  │ already_logged=True (locked by FR-012)│
                  └──────────────────────────────────────┘
                                  ▲
                                  │ (cannot transition out)
                                  │
   ┌───────────────┐  skip   ┌───────────────┐  include  ┌───────────────┐
   │ included=True │ ──────▶ │ included=False│ ────────▶ │ included=True │
   │ hours=N       │         │ hours=N       │           │ hours=N       │
   └───────────────┘ ◀────── └───────────────┘           └───────────────┘
            │  edit hours
            ▼
   ┌───────────────┐
   │ included=True │
   │ hours=N'      │
   └───────────────┘
```

Rows where `already_logged=True` are immutable in the preview — the UI does
not expose Skip/Include/Edit options for them (FR-012).

**Validation**:

- `date` must satisfy `date.weekday() < 5` (Mon=0..Fri=4) — weekends are
  excluded at construction time (FR-005, FR-014) and the constructor must
  refuse weekend dates as a defense-in-depth check.
- `hours` ≥ 0 and ≤ 8 (FR-008).
- `existing_hours_total` ≥ 0.
- When `already_logged == True`, the row must also satisfy `included == False`
  and is immutable for the rest of its lifetime.

---

## `SubmissionBatch`

The payload the CLI sends to `POST /activities/bulk` after the user approves
the preview.

| Field | Type | Notes |
|-------|------|-------|
| `project_id` | `int` | Same for every row in v1 (single-project assumption). |
| `task_id` | `int` | Same for every row in v1. |
| `description` | `str` | Fixed `"Administration"` in v1 (see research.md §5). |
| `billable` | `bool` | Fixed `False` in v1. |
| `entries` | `list[PlannedEntry]` | All entries where `is_submitable` is `True`. |

**Validation**:

- `len(entries) > 0`. If empty, the CLI refuses to submit and exits with
  code `5` (edge case in spec).
- All `entries[i].date` values are unique (no duplicates) and fall inside
  the chosen month.

**Serialization to the Moco bulk endpoint** (see `contracts/moco-http.md`):

```json
{
  "activities": [
    {
      "date": "2026-06-01",
      "project_id": 123,
      "task_id": 456,
      "seconds": 28800,
      "description": "Administration",
      "billable": false
    }
  ]
}
```

---

## `SubmissionResult`

Per-row outcome of the bulk call, surfaced to the user (FR-011).

### `EntryResult`

| Field | Type | Notes |
|-------|------|-------|
| `date` | `datetime.date` | The date this result corresponds to (mirrors `PlannedEntry.date`). |
| `status` | `Literal["created", "failed"]` | `"created"` only when Moco confirms creation of this row. |
| `error_message` | `str \| None` | Per-row failure reason when `status == "failed"` and Moco surfaces one; `None` on success. |

### `SubmissionResult`

| Field | Type | Notes |
|-------|------|-------|
| `entries` | `list[EntryResult]` | One entry per row that was sent (in the same order as the `SubmissionBatch`). |

**Derived properties** (not fields):

- `created_count`: `sum(1 for e in entries if e.status == "created")`.
- `failed_count`: `sum(1 for e in entries if e.status == "failed")`.
- `succeeded`: `failed_count == 0 and created_count == len(entries)`.
- `any_created`: `created_count > 0`.

**Rendering rules** (FR-011):

- All `"created"` → CLI prints the success line and exits `0`.
- All `"failed"` → CLI prints "Bulk submission failed; no entries were
  created." and exits `6` (research.md §6).
- Mixed → CLI prints "Created M of N entries for `<YYYY-MM>`. Failed: …"
  with the list of failed dates and reasons, and exits `7` (research.md §6).
  The user is told that re-running the CLI will retry only the still-missing
  dates (via FR-012's "already logged" exclusion).

**Construction from a `POST /activities/bulk` response**: when Moco's response
includes per-row status data, `entries` mirrors it. When the response is
opaque (the documented atomic-failure case), every row inherits the same
status: `"created"` for an overall 2xx, `"failed"` (with the upstream error
as the shared `error_message`) for a non-2xx or transport error.

---

## Relationships

```
ApiCredentials ──▶ (used by) ──▶ MocoClient
                                    │
                                    ├──▶ GET /session   → identifies user
                                    ├──▶ GET /projects/assigned → Project[] (each with Task[])
                                    ├──▶ GET /activities         → already-logged dates
                                    └──▶ POST /activities/bulk   → SubmissionResult

Project (chosen) ──┐
Task (chosen)    ──┤──▶ build PlannedEntry[] (one per weekday, merged with already-logged)
Month (chosen)   ──┘
                       │
                       ▼ user navigates / edits in preview
                  PlannedEntry[] (final)
                       │
                       ▼ on approval
                  SubmissionBatch ──▶ MocoClient.bulk_create() ──▶ SubmissionResult
```
