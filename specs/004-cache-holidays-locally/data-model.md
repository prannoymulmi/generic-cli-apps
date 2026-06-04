# Data Model: Cache Hamburg Holidays Locally After One Download

**Feature**: 004-cache-holidays-locally (bundled with 003-hamburg-holidays-skip)

**Date**: 2026-06-04

This feature introduces **one** new in-memory dataclass and extends
**one** existing dataclass. Every other dataclass from
`specs/001-create-mvp-moco-filler-app/data-model.md` is reused
unchanged. The on-disk cache schema is a separate concern documented
in [`contracts/holiday-cache.md`](./contracts/holiday-cache.md).

---

## `Holiday` (new — in-memory only)

A single (date, German name) pair as produced by the validator
(`research.md` §6) and consumed by the planner.

```python
from dataclasses import dataclass
from datetime import date as _date

@dataclass(frozen=True)
class Holiday:
    """One Hamburg public holiday in the requested year.

    Produced by ``holidays._validate_response`` after filtering the
    Nager.Date response to Hamburg-applicable entries (federal +
    DE-HH). Frozen so the catalogue is safe to hand to the planner
    by reference.
    """
    date: _date
    name: str
```

**Validation**:

- `date` MUST be a real `datetime.date` (not a string).
- `name` MUST be a non-empty string (the German `localName` from the
  source).
- The dataclass is `frozen=True` — once constructed, identity is
  fixed.

**Lifetime**: produced once per CLI run when the catalogue is loaded
(from cache or freshly fetched), discarded at process exit. Never
persisted directly — the on-disk shape is the JSON cache file (see
contracts).

**Where it lives**: `src/moco_filler/holidays.py` only. The planner
consumes it as a `dict[date, str]` (a derived view computed by
`get_hamburg_holidays`), so `Holiday` itself does not appear in
`planner.py`.

---

## `PlannedEntry` (existing, **extended** by this feature)

The existing dataclass from
`specs/001-create-mvp-moco-filler-app/data-model.md` § `PlannedEntry`
gains **one** new optional field:

```python
@dataclass
class PlannedEntry:
    date: _date
    weekday: str
    existing_hours_total: Decimal
    hours: Decimal
    included: bool
    already_logged: bool
    note: Optional[str] = None
    holiday_name: Optional[str] = None   # ← NEW in feature 003 / 004
```

**Semantic states** (derived from the combination of
`holiday_name`, `already_logged`, and `included`):

| `holiday_name` | `already_logged` | `included` | Resulting state | Submitable? |
|----------------|------------------|------------|-----------------|-------------|
| `None` | `True` | `False` | normal already-logged (feature 001 FR-012) | No |
| `None` | `False` | `True` (with existing > 0) | top-up | Yes |
| `None` | `False` | `True` (with existing == 0) | planned | Yes |
| `None` | `False` | `False` | user-skipped | No |
| `str` | `True` | `False` | already-logged with holiday metadata preserved (FR-005) | No |
| `str` | `False` | `False` | **auto-skipped Hamburg holiday** (the new state — FR-002 / FR-003) | No |
| `str` | `False` | `True` (with existing > 0) | overridden holiday → renders as top-up (FR-006) | Yes |
| `str` | `False` | `True` (with existing == 0) | overridden holiday → renders as planned (FR-006) | Yes |

**Construction-time invariants** (`__post_init__`):

- The existing four invariants from feature 001 (weekday, non-
  negative existing-hours, hours in `[0, 8]`, locked-rows-not-
  included) remain unchanged.
- One new invariant for the holiday extension:
  - **When `holiday_name is not None`, the date MUST be a real
    Hamburg public holiday for `self.date.year`** — i.e., callers
    are expected to set this field only via `planner.build_planned_entries`,
    which sources it from the catalogue.
  - This invariant is not enforced inside `__post_init__` (the
    planner has the catalogue; the dataclass does not). It is
    asserted at the planner boundary (see `planner.build_planned_entries`
    contract below).

**Migration concern**: every existing call site that constructs a
`PlannedEntry` omits `holiday_name`. Because the field defaults to
`None`, existing tests and existing planner code paths continue to
produce non-holiday rows unchanged — feature 002's preview keeps
working without any update to call sites it doesn't need to touch.

---

## `planner.build_planned_entries` (existing function, extended signature)

The existing signature:

```python
def build_planned_entries(
    year: int,
    month: int,
    existing_activities: Iterable[Dict[str, Any]],
) -> List[PlannedEntry]: ...
```

becomes:

```python
def build_planned_entries(
    year: int,
    month: int,
    existing_activities: Iterable[Dict[str, Any]],
    holiday_catalogue: Mapping[date, str] = {},   # ← NEW
) -> List[PlannedEntry]: ...
```

The new parameter accepts a mapping of `date → holiday name`. An
empty mapping is the FR-007 / FR-013 graceful fallback shape (no
holidays marked).

**Behaviour**:

- For each weekday `d` in the month:
  - If `d in holiday_catalogue` AND the row's existing-hours state
    would otherwise be `planned` or `top-up` (i.e., not
    `already_logged`), set `holiday_name = holiday_catalogue[d]`,
    `included = False`, `hours = 0`, `note = f"Holiday: {name}"`.
  - If `d in holiday_catalogue` AND the row is `already_logged`,
    set `holiday_name = holiday_catalogue[d]` but leave
    `already_logged = True` and `included = False` — the
    `already_logged` state wins per FR-005, with the holiday name
    preserved as metadata.
  - Otherwise (d not in catalogue) the row is built as it was
    before this feature.

**Rationale**: the planner is the single place that owns row
construction; passing the catalogue in keeps the planner pure
(no `holidays.get_hamburg_holidays` import inside `planner.py`)
and makes the holiday-vs-already-logged precedence rule a
two-line conditional that's easy to unit-test.

---

## `planner.toggle_skipped` (existing function, behaviour extended)

The existing signature is unchanged:

```python
def toggle_skipped(row: PlannedEntry) -> PlannedEntry: ...
```

The new behaviour layer:

- Toggling a holiday row from `included=False` (auto-skipped) to
  `included=True` MUST preserve `holiday_name` on the returned
  entry. The override is recorded in the `included` flag only.
- Toggling a holiday row from `included=True` (overridden) back to
  `included=False` MUST also preserve `holiday_name` and MUST set
  `hours = 0` so the row returns to its canonical holiday-skipped
  state (FR-007).
- Toggling an already-logged + holiday row still raises
  `ValueError` (the existing FR-012 lock from feature 001 applies
  to any already-logged row regardless of holiday status).

**Implementation**: trivially `dataclasses.replace(row, included=not row.included)`
already preserves `holiday_name` because `replace` copies all
unmentioned fields. The only **new** code path is the
"`hours = 0` when toggling back to skipped" branch, which we'll
add explicitly for symmetry with the `set_hours` rule.

---

## `planner.set_hours` (existing function, behaviour unchanged)

Already handles the `hours == 0` → `included = False` auto-skip rule
from feature 001. Setting hours on a holiday row that has been
overridden is allowed (it's a regular included row at that point);
setting hours on an already-logged + holiday row still raises
`ValueError`. No code change needed.

---

## Relationships

```
date.nager.at  ─── HTTPS GET (fetch once per year) ─►  holidays._fetch_with_retry
                                                              │
                                                              ▼
                                         _validate_response (FR-016)
                                                              │
                                                              ▼
                              list[Holiday]                                       holidays.json
                                  │                              ▲                      │
                                  ▼                              │                      ▼
                          _save_cache  ──────► JSON-on-disk ─────┘            _load_cache
                                                                                       │
                                  ┌───────────── dict[date, str] ◀────────────────────┘
                                  ▼
                  planner.build_planned_entries(year, month, activities, holiday_catalogue)
                                  │
                                  ▼
                         List[PlannedEntry]  (with holiday_name set where applicable)
                                  │
                                  ▼
                         styling.format_styled_row  ──► row.holiday class
                                  │
                                  ▼
                         questionary.select  ──► user sees auto-skipped + named row
```

The data flow is one-way: Nager → on-disk cache → in-memory map →
PlannedEntry → preview. Nothing in the preview writes back into the
catalogue or the cache file.

---

## Lifetime

| Object | Lifetime |
|--------|----------|
| `Holiday` instance | One CLI run (built from cache or fetch, dropped at exit) |
| `holiday_catalogue` (`dict[date, str]`) | One CLI run |
| `holiday_name` on `PlannedEntry` | One CLI run (the row itself is per-run) |
| The on-disk `holidays.json` cache file | Indefinite — until the user deletes it or the schema version changes |
| `requests.Session` used by `holidays.py` | One CLI run (lazy-constructed on first cold-cache fetch; never used on cache hits) |
