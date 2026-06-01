# Implementation Plan: Moco Monthly Time Tracker CLI

**Branch**: `001-moco-time-tracker` | **Date**: 2026-06-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-moco-time-tracker/spec.md`

## Summary

Build an interactive Python 3 CLI (`moco-filler`) that fills a chosen month of
Moco time entries — 8 hours/day, Mon–Fri — for one project + one task
(defaulting to `"Administration"`). The tool authenticates with a personal
API key supplied via env var or masked prompt (never persisted to disk),
fetches projects and tasks from `GET /projects/assigned`, sums the user's
existing entries per date across **all** projects/tasks (via
`GET /activities`) to lock days already at ≥ 8h and auto top up partial
days, shows a keyboard-navigable Questionary preview where the user can
skip rows or edit hours within `[0, 8]`, and on explicit approval sends one
`POST /activities/bulk` request. On cancel, nothing is created; on
submission failures, the CLI reports per-row outcomes (FR-011) so that
re-runs retry only the still-missing dates via the "already logged"
exclusion. See [`research.md`](./research.md) for the decisions behind each
of these choices.

## Technical Context

**Language/Version**: Python 3.11 (constitution requires ≥ 3.9; we pin to
3.11 in `pyproject.toml` for dev to keep behavior reproducible).

**Primary Dependencies**:

- `questionary` — every interactive prompt, including the preview's
  arrow-key navigation (constitution §I).
- `requests` — Moco HTTP calls, with explicit 15s timeouts.
- Standard library only for date math (`datetime`, `calendar`).

**Dev Dependencies**: `pytest`, `responses` (HTTP mocking for unit tests).

**Storage**: None — the API key and all session state live in memory for the
duration of one run (FR-001).

**Testing**: `pytest`. Unit tests for `calendar_utils`, `planner`,
`moco_client` (HTTP mocked), `models`, and the pure functions extracted from
`preview`. No integration tests for MVP (constitution §IV).

**Target Platform**: macOS / Linux terminal with basic ANSI styling and a
keyboard. Headless/scripted use is explicitly out of scope (spec
Assumptions).

**Project Type**: Single CLI application — one Python package, no
client/server split.

**Performance Goals**: No throughput target — the workload is one user, four
HTTP calls per run. The happy path must complete in under 2 minutes on a
responsive network (SC-001).

**Constraints**:

- API key MUST NOT touch the filesystem (FR-001, SC-004).
- Weekends MUST NEVER appear in the preview or in any submission (FR-014,
  SC-002).
- No data is sent to Moco until the user invokes the explicit
  `Approve & submit` action (FR-009, SC-006).

**Scale/Scope**: At most ~23 rows per run (max weekdays in a month), one
project + one task per run.

## Constitution Check

*Re-checked after Phase 1 design — gates still pass.*

| Principle | How this plan satisfies it |
|-----------|----------------------------|
| **I. Python3 & Questionary-First** | All interactive prompts (password, project picker, task picker, month input, preview, per-row sub-menu, hours edit) use Questionary primitives. No alternative prompt or TUI library is introduced. |
| **II. Atomic Commits** | Process-level discipline enforced at commit time, not by code structure. The upcoming `tasks.md` will be sliced so each task maps to one atomic commit; module boundaries below (`auth`, `moco_client`, `calendar_utils`, `planner`, `preview`, `cli`) make this natural. |
| **III. Clean Code & Readability** | Each module has a single, named purpose. Type hints across public functions. Comments reserved for non-obvious "why" (per constitution wording). No deep nesting — the preview loop dispatches on row state via small named helpers. |
| **IV. Unit Tests Only** | `pytest` covers business logic: weekday enumeration, planner merge with already-logged set, edit/skip transitions, HTTP-client request shaping (mocked with `responses`), exit-code mapping. No integration tests against real Moco. |
| **V. Single Responsibility & Modularity** | CLI module is thin glue; HTTP, calendar math, planning, and the preview UI live in separate modules. Questionary calls are confined to `cli.py` and `preview.py`; business logic modules have no UI imports, keeping them unit-testable. |

**Gate result**: PASS. No violations; `Complexity Tracking` table is left empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-moco-time-tracker/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output — Moco API + UX decisions
├── data-model.md        # Phase 1 output — in-memory entities
├── quickstart.md        # Phase 1 output — install → fill a month
├── contracts/
│   ├── cli.md           # External CLI surface this tool exposes
│   └── moco-http.md     # The Moco endpoints this tool consumes
├── spec.md              # Feature spec (already accepted)
└── tasks.md             # Phase 2 output — written by /speckit-tasks, NOT here
```

### Source Code (repository root)

The repo currently contains only `CLAUDE.md` and `specs/`. This plan
introduces the application package under `src/moco_filler/` with tests
adjacent in `tests/`, matching the constitution's modularity guidance (§V)
and unit-test discipline (§IV).

```text
src/
└── moco_filler/
    ├── __init__.py
    ├── __main__.py        # `python -m moco_filler` entry → cli.main()
    ├── cli.py             # argparse + Questionary glue; entrypoint
    ├── auth.py            # Resolve API key from env var or masked prompt
    ├── moco_client.py     # requests-based HTTP layer (4 endpoints)
    ├── calendar_utils.py  # Weekday enumeration for a chosen month
    ├── planner.py         # Build PlannedEntry[], merge already-logged, apply edits
    ├── preview.py         # Questionary preview loop + sub-menu dispatch
    ├── models.py          # Dataclasses for Project, Task, PlannedEntry, etc.
    └── errors.py          # Domain exceptions mapped to exit codes

tests/
├── test_calendar_utils.py
├── test_planner.py
├── test_models.py
├── test_moco_client.py    # HTTP mocked via `responses`
└── test_preview_logic.py  # Pure logic only; live Questionary loop not unit-tested

pyproject.toml             # Defines `moco-filler` console script + deps
requirements.txt           # Pinned versions (mirrors pyproject for reproducibility)
README.md                  # Pointer to specs/001-moco-time-tracker/quickstart.md
```

**Structure Decision**: Single project layout under `src/moco_filler/`.
Rationale:

- The spec describes one CLI with no library users and no second
  deliverable, so the constitution's preference for "minimize external
  dependencies" and "single responsibility" maps cleanly onto a single
  package.
- `src/` layout (instead of a flat `moco_filler/` at the root) keeps the
  installed package importable only after `pip install -e .`, which catches
  "works on my machine because of `sys.path`" bugs early.
- The eight module files above each correspond to exactly one concern from
  the spec (auth, HTTP, dates, planning, preview UI, CLI glue, data
  classes, errors), keeping each module independently reviewable and
  unit-testable.

## Complexity Tracking

> No constitution violations to justify; this section is intentionally empty.
