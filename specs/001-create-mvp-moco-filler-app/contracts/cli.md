# Contract: CLI Surface

**Feature**: 001-create-mvp-moco-filler-app
**Date**: 2026-06-01

This is the **external** contract this project exposes — the command the user
runs in their terminal. It is the equivalent of an API contract for a library:
breaking it is a breaking change for users.

---

## Invocation

```
moco-filler [--month YYYY-MM]
```

| Element | Required | Default | Notes |
|---------|----------|---------|-------|
| Executable name | yes | `moco-filler` | Installed via the project's `pyproject.toml` `[project.scripts]` entry. |
| `--month` | no | Current calendar month at startup | Format strictly `YYYY-MM`. Invalid formats exit `1` with a usage message. |

No other flags are accepted in v1. In particular:

- No `--api-key` flag — credentials always come from env or masked prompt
  (see "Environment" below).
- No `--project` / `--task` flags — selection is always interactive in v1.

---

## Environment

| Variable | Purpose |
|----------|---------|
| `MOCO_API_KEY` | If set and non-empty, used as the API token and the masked prompt is skipped. Never written or echoed by this tool. |

No other env vars are read in v1.

---

## Interactive flow (happy path)

The user-visible sequence the CLI guarantees:

1. **(Only if `MOCO_API_KEY` unset)** Masked password prompt:
   `"Moco API key:"`
2. Project picker (`questionary.select`) listing every project from
   `GET /projects/assigned`. Sorted by project name.
3. Task picker (`questionary.select`) listing tasks of the chosen project.
   Defaulted to a task literally named `"Administration"` if one exists.
4. Month prompt — skipped when `--month` was supplied. When asked, format is
   `YYYY-MM`, default-filled with the current month.
5. Preview screen rendered as a `questionary.select` whose choices are:
   - One choice per Mon–Fri date of the chosen month, formatted like
     `"Wed 2026-06-03   8.00h   [planned]"` (empty day, full 8h) or
     `"Wed 2026-06-03   3.50h   [top-up: existing 4.50h]"` (partial day —
     planned hours = `8 − existing_total`, FR-012) or
     `"Wed 2026-06-03   0.00h   [already logged]"` (day full, ≥ 8h existing —
     locked, FR-012) or
     `"Wed 2026-06-03   0.00h   [skipped]"`.
   - A separator line.
   - `"✅ Approve & submit"`.
   - `"❌ Cancel"`.
6. Selecting a data row opens a sub-menu. Available options depend on row
   state:
   - **Plain planned row** (empty day): `Skip this row` / `Change hours` /
     `Back`.
   - **Top-up row** (partial day): `Skip this row` / `Change hours` / `Back`.
     Behaves identically to a plain planned row; only the default hours and
     the row label differ.
   - **Skipped row**: `Include this row` / `Change hours` / `Back`.
   - **Already-logged row**: `Back` only (FR-012).
7. On `Approve & submit`, the CLI calls `POST /activities/bulk` once with
   the submitable rows and prints a per-row outcome line (FR-011 — full
   success, total failure, or partial failure).
8. On `Cancel` (or quit / Ctrl-C at any prompt), the CLI exits without
   calling `POST /activities/bulk`.

---

## stdout / stderr contract

Lines printed to **stdout** that other tooling MAY scrape (kept short and
stable on purpose):

| When | Line |
|------|------|
| Successful bulk submit (every row created) | `Created N entries in Moco for <YYYY-MM>.` |
| Partial bulk submit (some rows created, some failed — FR-011) | `Created M of N entries for <YYYY-MM>. Failed: <date> (<reason>), …` |
| Total bulk failure (no rows created) | `Bulk submission failed; no entries were created.` |
| User cancelled at preview | `Nothing was submitted.` |
| Edge case: every row skipped | `No entries to submit; exiting.` |

**stderr** is reserved for error messages and noisy diagnostics. No secrets
are ever written to either stream.

---

## Exit codes

| Code | Meaning | Triggered by |
|------|---------|--------------|
| `0` | Success, or clean user cancel | Happy path, or `Cancel` / Ctrl-C at preview |
| `1` | Bad CLI input | Invalid `--month` value, etc. |
| `2` | Authentication failed | `GET /session` returns 401/403 |
| `3` | No projects | `GET /projects/assigned` returns `[]` |
| `4` | No tasks in chosen project | Chosen project has empty `tasks` |
| `5` | Nothing left to submit | User skipped every otherwise-submitable row |
| `6` | Bulk submission total failure | No rows created — network failure, non-2xx from `POST /activities/bulk`, or all rows failed per the per-row response |
| `7` | Bulk submission partial failure | Some rows created, others failed (per-row response from `POST /activities/bulk`) — FR-011, clarification 2026-06-01 |

(These come straight from `research.md` §6.)

---

## What the CLI must NOT do

These are negative-space guarantees, derived from the spec's FRs and SCs:

- MUST NOT create any file in the project directory or anywhere else that
  contains the API key (FR-001, SC-004).
- MUST NOT include weekend dates in the preview or in the submission, even
  if the user tries to edit them in (FR-014).
- MUST NOT toggle an `already_logged` row back into `included` (FR-012).
- MUST NOT send any HTTP request to Moco between "user cancels preview" and
  process exit (FR-009, SC-006).
- MUST NOT print the API key to stdout, stderr, or any log line, ever.
