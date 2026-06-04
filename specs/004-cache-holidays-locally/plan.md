# Implementation Plan: Cache Hamburg Holidays Locally After One Download

**Branch**: `004-cache-holidays-locally` | **Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-cache-holidays-locally/spec.md`

## Summary

Add Hamburg public-holiday awareness to the moco-filler preview by
introducing a small new module (`src/moco_filler/holidays.py`) that
fetches the year's holidays once from a public source, persists the
result to a per-user on-disk cache, and feeds the planner so holiday
weekdays are auto-skipped and labelled with their German name in the
preview.

This plan implements **both** open features simultaneously:

- **Feature 003 — `003-hamburg-holidays-skip`**: the user-visible side
  (detection, skip, named-holiday row, override flow, already-logged
  precedence).
- **Feature 004 — `004-cache-holidays-locally`**: the source-and-caching
  side (fetch once, cache locally, retry with budget, graceful
  fallback, stderr status line).

Bundling is deliberate: 004's spec explicitly amends 003's
"bundled-catalogue" assumption, and neither feature ships value
without the other. The implementation lives in one module
(`holidays.py`) plus thin extensions to `planner.py`, `models.py`,
`styling.py`, `preview.py`, and `cli.py`. No new top-level dependency
is introduced — `requests` is already pinned for the Moco HTTP client
(see `src/moco_filler/moco_client.py`).

Per the clarification session on 2026-06-04, the fetch path uses
**three attempts** with per-attempt timeout ~1.5 s and a total
wall-clock budget ~5 s; failures funnel through one shared retry
loop. The user-visible behaviour from feature 003 (auto-skip, named
row, override) is unchanged by 004 — only the source of the holiday
list moves from "compiled in" to "fetched once, cached locally".

## Technical Context

**Language/Version**: Python 3.11 (already pinned in `pyproject.toml`
from feature 001; ≥ 3.9 per Constitution §I).

**Primary Dependencies**:

- `requests` (already shipped via `moco_client.py`) — used for the
  one-time-per-year HTTP fetch from the holiday source.
- `questionary` (already shipped) — unchanged. The new holiday
  state slots into the existing `Style.from_dict` palette from
  feature 002.
- Standard library only for cache I/O (`json`, `os`, `pathlib`,
  `tempfile`, `datetime`, `time`, `sys`).

**Storage**:

- One JSON file at the standard per-user cache directory for the
  host OS (`~/Library/Caches/moco-filler/holidays.json` on macOS,
  `${XDG_CACHE_HOME:-$HOME/.cache}/moco-filler/holidays.json` on
  Linux, `%LOCALAPPDATA%\moco-filler\Cache\holidays.json` on
  Windows). One file holds **all** (region, year) entries so the
  cache grows by one inner key per new year the user previews.
- Human-readable. Inspectable / deletable with ordinary OS file
  tooling (FR-010).

**Testing**: `pytest`. New unit tests for the holidays module
(catalogue parsing, validator, retry loop, cache read/write, atomic
overwrite, schema-mismatch handling). The HTTP boundary is faked
with a stub `requests.Session` per-test; the real `date.nager.at`
endpoint is **never** contacted from the test suite (per Constitution
§IV unit-only mandate).

**Target Platform**: macOS / Linux / Windows terminal — same as
feature 001. The cache directory is the only OS-specific concern;
the per-OS branch keeps it stdlib-only.

**Project Type**: Single CLI application — same Python package
`src/moco_filler/`; no client/server split.

**Performance Goals**: human-interactive scale. Per SC-002 the
cache-hit path must add no more than 100ms of startup overhead; in
practice the cache hit is a single JSON load (< 10ms on warm disks).
The cold-cache worst-case is bounded at ~5 s (FR-008/FR-017) and
the FR-015 stderr status line is what keeps that wait from feeling
like a freeze.

**Constraints**:

- No new top-level dependency (FR-010 in spec).
- Cache file MUST NOT contain user-private data (FR-009).
- Cache MUST be atomically updated so concurrent CLI invocations
  cannot corrupt it (FR-013).
- Cold-cache fetch path bounded at ~5 s wall-clock (FR-008) with
  per-attempt timeout ~1.5 s (FR-008/FR-017).
- The stdout-scrape contract from
  `specs/001-create-mvp-moco-filler-app/contracts/cli.md` is
  untouched; the FR-015 status line goes to **stderr** only.
- The Questionary-only mandate (Constitution §I) holds — the new
  module is non-interactive.

**Scale/Scope**: ~10 holidays per year for Hamburg; the cache file
sits well under 100 KB per supported year (SC-006). The catalogue
the planner consults at runtime is a tiny `dict[date, str]` of size
≤ 10. The retry budget is the only non-trivial timing surface.

## Constitution Check

*Initial gate — re-checked after Phase 1 design; both gates pass.*

| Principle | How this plan satisfies it |
|-----------|----------------------------|
| **I. Python3 & Questionary-First** | No new TUI library. The new `holidays.py` is non-interactive (no Questionary calls). The user-visible holiday row reuses feature 002's existing `Style.from_dict` palette via one new `row.holiday` class. |
| **II. Atomic Commits** | The work decomposes into small commits — each landing one of: a stub module + its tests, a planner hook + its tests, a model field + its test, a styling token + its test, a preview branch + its test, a cli wiring change. Each commit leaves `pytest` green. |
| **III. Clean Code & Readability** | `holidays.py` exposes a small named API: `get_hamburg_holidays(year) -> dict[date, str]`, `_fetch_from_source(year) -> list[Holiday]`, `_load_cache() / _save_cache()`, `_validate_response()`. Each is single-purpose and type-hinted. |
| **IV. Unit Tests Only** | Validator, parser, retry loop, cache I/O, schema-mismatch, atomic-write, planner integration are all pure-Python and unit-testable. The live network call is **never** exercised from tests — a fake session is injected. |
| **V. Single Responsibility & Modularity** | `holidays.py` owns the catalogue + cache; `planner.py` gains one line that consults `get_hamburg_holidays`; `models.py` gains one optional field on `PlannedEntry`; `styling.py` gains one style class; `preview.py` gains one branch; `cli.py` gains one call. Nothing imports `requests` outside `moco_client.py` and `holidays.py`. |

**Gate result**: PASS. No violations; the `Complexity Tracking`
section is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/004-cache-holidays-locally/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 — source pick, cache dir, retry shape, validation
├── data-model.md        # Phase 1 — Holiday entity + extended PlannedEntry
├── quickstart.md        # Phase 1 — where the cache lives, how to clear it
├── contracts/
│   ├── holiday-source.md   # External source response contract (subset we depend on)
│   └── holiday-cache.md    # On-disk cache file schema (v1)
├── checklists/
│   └── requirements.md  # Already PASS-ing
├── spec.md              # Feature spec (clarifications integrated)
└── tasks.md             # Phase 2 output — written by /speckit-tasks, NOT here
```

### Source Code (repository root)

One new module, four lightly-modified existing modules, one new test
file plus two updated test files.

```text
src/
└── moco_filler/
    ├── __init__.py
    ├── __main__.py
    ├── cli.py              # (modified) one new call to fetch holidays before preview
    ├── auth.py
    ├── moco_client.py
    ├── calendar_utils.py
    ├── planner.py          # (modified) consults the catalogue when building rows
    ├── preview.py          # (modified) one new branch in the row-state derivation
    ├── styling.py          # (modified) one new style class `row.holiday`
    ├── holidays.py         # (NEW) source fetch + cache I/O + catalogue accessor
    ├── models.py           # (modified) PlannedEntry gains `holiday_name: Optional[str]`
    └── errors.py

tests/
├── test_calendar_utils.py
├── test_planner.py         # (modified) +cases for holiday rows + already-logged precedence
├── test_models.py          # (modified) +case for the new optional field default
├── test_moco_client.py
├── test_auth.py
├── test_preview_logic.py   # (modified) +case for the new holiday state label
├── test_styling.py         # (modified) +case for the new `row.holiday` class
└── test_holidays.py        # (NEW) source-parse, validator, retry, cache I/O, planner glue
```

**Structure Decision**: Reuse the single-project layout from features
001 and 002. Rationale:

- The new logic fits in one module (`holidays.py`), so a sub-package
  would over-structure the addition.
- The on-disk cache touches one file at one path — no `cache/`
  subpackage is justified for a single JSON file.
- The new test file (`test_holidays.py`) follows the existing
  one-test-per-module convention from feature 001.

## Complexity Tracking

> No constitution violations to justify; this section is intentionally empty.
