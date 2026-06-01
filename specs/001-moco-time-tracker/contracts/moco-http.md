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

Used to detect dates that already have an activity recorded against the
chosen project + task for the current user (FR-012).

**Query parameters we send**:

| Param | Value |
|-------|-------|
| `from` | `YYYY-MM-01` of chosen month |
| `to` | last day of chosen month, `YYYY-MM-DD` |
| `project_id` | chosen project id |
| `task_id` | chosen task id |
| `user_id` | current user's id from `GET /session` |

**Response (200) — fields we depend on**:

```json
[
  { "date": "2026-06-03", "hours": 4.0 }
]
```

We use only `date`. The set of `date` values becomes the "already logged"
set; any matching `PlannedEntry.date` flips `already_logged=True`.

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

**Success response (2xx)**:

We treat any 2xx as success. The CLI prints
`"Created N entries in Moco for <YYYY-MM>."` where `N` is the number of
rows we sent — Moco's response shape for the bulk endpoint is treated as
opaque in v1.

**Failure response (non-2xx, or transport error)**:

Maps to exit code `6`. The CLI prints `"Bulk submission failed; no entries
were created."` and includes the upstream status code / error body, if any,
on stderr.

---

## Change-detection notes (for future-us)

If any of the following stops being true upstream, this contract — and the
code that depends on it — must be revisited:

- `Authorization: Token token=…` header format.
- `tasks` embedded in `/projects/assigned`.
- `POST /activities/bulk` accepts a `{ "activities": [...] }` envelope.
- `seconds` (not `hours`) is the duration field on the bulk payload.
