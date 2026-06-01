# Contract: Moco HTTP API (consumed)

**Feature**: 001-moco-time-tracker
**Date**: 2026-06-01

This is the **inbound** dependency contract — the shape of the Moco API
endpoints this tool relies on. We don't own this API; this document fixes
the subset we depend on so changes upstream can be detected.

Source: <https://everii-group.github.io/mocoapp-api-docs/sections/activities.html>

---

## Base

- **Base URL** (this user): `https://statista.mocoapp.com/api/v1`
- **Auth header** (every request): `Authorization: Token token=<API_KEY>`
- **Content type** (POST bodies): `application/json`
- **Timeout** (every call from this client): 15s

---

## `GET /session`

Identifies the authenticated user. Called once at startup so we can scope
the "already logged" filter to the current user.

**Response (200) — fields we depend on**:

```json
{
  "id": 12345,
  "firstname": "...",
  "lastname": "...",
  "email": "..."
}
```

We use only `id` (as `user_id` in later filters). Other fields are ignored
but tolerated.

**Failure modes we handle**:

- `401` / `403` → exit `2` ("Authentication failed").
- Any other non-2xx → exit `6` with the status code in the error message.

---

## `GET /projects/assigned`

Returns every project the authenticated user can book time against, with
tasks embedded.

**Response (200) — fields we depend on**:

```json
[
  {
    "id": 123,
    "name": "Internal",
    "tasks": [
      { "id": 456, "name": "Administration" },
      { "id": 457, "name": "Meetings" }
    ]
  }
]
```

Empty array → exit `3` ("No projects").
Selected project with empty `tasks` → exit `4`.

---

## `GET /activities`

Used to compute the current user's existing-hours total per date across
**all** projects and tasks (FR-012, clarification 2026-06-01) so the
planner can lock days at ≥ 8h and auto-top-up partial days.

**Query parameters we send**:

| Param | Value |
|-------|-------|
| `from` | `YYYY-MM-01` of chosen month |
| `to` | last day of chosen month, `YYYY-MM-DD` |
| `user_id` | current user's id from `GET /session` |

We deliberately do **not** filter by `project_id` or `task_id` — the
"already logged" rule sums every entry the user has on a date regardless of
project/task. (Prior to the 2026-06-01 clarification this filter was scoped
to the chosen project/task; that is no longer the case.)

**Response (200) — fields we depend on**:

```json
[
  { "date": "2026-06-03", "hours": 4.0 }
]
```

We use both `date` and `hours`. For each in-month date we sum the `hours`
values across all returned rows and store the result on the corresponding
`PlannedEntry.existing_hours_total`. Days with a sum ≥ 8h flip
`already_logged=True` (locked); days with a sum > 0 but < 8h take a default
`hours` of `8 − existing_total` so the submission tops the day to 8h.

---

## `POST /activities/bulk`

The single bulk-create call invoked after the user approves the preview
(FR-010).

**Request body**:

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

Field rules:

- `date`: `YYYY-MM-DD` string, must be a weekday in the chosen month.
- `project_id` / `task_id`: integers from the user's earlier selection.
- `seconds`: integer; computed as `int(hours * 3600)`.
- `description`: fixed `"Administration"` in v1 (see research.md §5).
- `billable`: fixed `false` in v1.

**Response handling (FR-011 — per-row outcomes, clarification 2026-06-01)**:

We construct a `SubmissionResult` whose `entries` list mirrors the rows we
sent. Two response shapes are supported:

1. **Per-row response** — if Moco returns a JSON body where individual rows
   carry a status or error indicator, we map each one to an `EntryResult`
   with `status="created"` or `status="failed"` plus the per-row
   `error_message`.
2. **Opaque response** — if Moco's bulk endpoint behaves atomically (every
   2xx = all rows created, every non-2xx = no rows created), every
   `EntryResult` inherits the overall status. On failure they share the
   same `error_message` derived from the HTTP status and any response body.

Exit code follows the `SubmissionResult` rendering rules in
`data-model.md`:

| Outcome | stdout | Exit code |
|---------|--------|-----------|
| All rows created (`failed_count == 0`) | `Created N entries in Moco for <YYYY-MM>.` | `0` |
| All rows failed (`created_count == 0`) | `Bulk submission failed; no entries were created.` | `6` |
| Partial (`created_count > 0 and failed_count > 0`) | `Created M of N entries for <YYYY-MM>. Failed: <date> (<reason>) …` | `7` |

The upstream status code / error body is mirrored on stderr in failure and
partial-failure cases.

---

## Change-detection notes (for future-us)

If any of the following stops being true upstream, this contract — and the
code that depends on it — must be revisited:

- `Authorization: Token token=…` header format.
- `tasks` embedded in `/projects/assigned`.
- `POST /activities/bulk` accepts a `{ "activities": [...] }` envelope.
- `seconds` (not `hours`) is the duration field on the bulk payload.
