# Research: Cache Hamburg Holidays Locally After One Download

**Feature**: 004-cache-holidays-locally (bundled with 003-hamburg-holidays-skip)

**Date**: 2026-06-04

This document resolves every `NEEDS CLARIFICATION` item from
`plan.md` § Technical Context. Decisions here feed `data-model.md`,
`contracts/holiday-source.md`, `contracts/holiday-cache.md`, and
the upcoming `tasks.md`.

---

## 1. Which public holiday source to query

**Decision**: Use `https://date.nager.at/api/v3/PublicHolidays/{year}/DE`
— the free, public, no-auth-required Nager.Date public-holidays
endpoint, requesting the German calendar and filtering client-side
to the Hamburg subset (`counties == null` for federal holidays, or
`counties` containing `"DE-HH"` for Hamburg-specific entries).

**Rationale**:

- **Public + free + no auth** — matches the spec's "anonymous endpoint"
  assumption (`spec.md` § Assumptions).
- **Open source**, has been maintained since ~2016, used by many
  projects. Reasonable longevity bet for a one-fetch-per-year usage.
- **Subdivision support** — the response carries a `counties: ["DE-BY",
  "DE-HH", …]` array on regional holidays (notably Reformationstag,
  which is `["DE-BB", "DE-HB", "DE-HH", "DE-MV", "DE-NI", "DE-SN",
  "DE-ST", "DE-SH", "DE-TH"]`) so the FR-012 "Reformationstag from 2018
  onwards" rule is satisfied by the source itself — we don't have to
  hard-code Hamburg-specific dates anywhere.
- **JSON over HTTPS** — `requests` already in `moco_client.py` consumes
  it directly; no new dependency.

**Alternatives considered**:

- `python-holidays` library. Rejected: it adds a 1.5 MB transitive
  dependency and ships a hard-coded list that we'd be relying on for
  freshness — exactly the failure mode the user's "download once"
  request avoids. We'd be back to a bundled catalogue.
- `feiertage.io`. Rejected: German-only project, smaller maintainer
  team, no subdivision metadata in the v3 response (returns a flat
  list per region requiring a separate request per state). More
  fragile.
- A self-hosted JSON file in a GitHub repo we control. Rejected:
  someone has to maintain it. The whole point of fetching is to
  inherit someone else's maintenance.
- Computing Easter ourselves with `dateutil.easter` + hard-coded
  fixed dates. Rejected: this IS the bundled-catalogue approach
  feature 004 amends. Re-introducing it defeats the user's intent.

---

## 2. Where the cache file lives on each OS

**Decision**: Stdlib-only per-OS resolver — no `platformdirs`
dependency. The path is `<user_cache_dir>/moco-filler/holidays.json`
where `<user_cache_dir>` is:

| Platform | Path |
|----------|------|
| macOS (`sys.platform == "darwin"`) | `~/Library/Caches` |
| Linux (`sys.platform.startswith("linux")`) | `$XDG_CACHE_HOME` if set and non-empty, else `~/.cache` |
| Windows (`sys.platform == "win32"`) | `%LOCALAPPDATA%` if set, else `~/AppData/Local`, with `Cache` appended → `…/moco-filler/Cache/holidays.json` |
| Anything else | `~/.cache` (same as Linux fallback) |

The resolver is ~15 lines of pure Python and is unit-tested by
monkeypatching `sys.platform` and the relevant env vars.

**Rationale**:

- **Honours the standards each OS already publishes** (XDG on Linux,
  the Apple File System Programming Guide on macOS, MSDN on
  Windows) so the cache lives where the user / OS expects to find it
  for cleanup.
- **One dependency-free function**, ~15 lines, deterministic.
- **No `platformdirs`** — that crate is excellent but it's a new
  top-level dependency, which violates FR-010. The 15-line
  homebrew is enough for our three OSes.

**Alternatives considered**:

- The `platformdirs` library. Rejected per FR-010 (no new
  top-level dependency).
- Hard-coding `~/.cache/moco-filler/` on every OS. Rejected:
  works on Linux but lands the file in an unexpected spot on
  macOS / Windows; users hunting for it on macOS would expect
  `~/Library/Caches/`.
- Placing the cache inside the user's repo (`.moco-filler-cache/`).
  Rejected: would couple cache to working-directory, get
  re-fetched after each `git clone`, and risks being accidentally
  committed. Violates the spec's "per-user, per-machine" intent.

---

## 3. On-disk cache file format

**Decision**: A single JSON file with a versioned schema:

```json
{
  "schema_version": 1,
  "regions": {
    "DE-HH": {
      "2026": {
        "fetched_at": "2026-06-04T11:42:17Z",
        "holidays": [
          {"date": "2026-01-01", "name": "Neujahrstag"},
          {"date": "2026-04-03", "name": "Karfreitag"},
          {"date": "2026-04-06", "name": "Ostermontag"},
          ...
        ]
      }
    }
  }
}
```

A miss is any of: file missing, JSON parse failure, top-level
`schema_version` missing or ≠ `1`, the `regions.<region>.<year>`
key not present, or the inner `holidays` value malformed.

**Rationale**:

- JSON over the stdlib `json` module — zero new dependencies,
  human-readable (FR-010 hard-requirement), easy to inspect with
  `cat | jq`.
- **`schema_version`** at the top level — a future change can bump
  to `2` and old caches are detected as a miss instantly (FR-006 /
  Edge Case "old cache schema").
- **`regions` is a map of region → year → entry** so a single file
  scales to many (region, year) pairs without rewriting unrelated
  entries (FR-004 / FR-012). One-file-per-year was considered but
  rejected: ten years of Hamburg holidays is ~5 KB total, so a
  single file is simpler to atomic-write and inspect.
- **`fetched_at` is ISO-8601 UTC** — useful for diagnostics
  ("when did we last refresh?") without giving us a stale-cache
  invalidation hook (FR-011 says "no auto-refresh inside a year").
- **The on-disk `holidays` array preserves the source's ordering**
  but the runtime API is `dict[date, name]` — order in the file
  is informational only.

**Alternatives considered**:

- Pickle. Rejected: opaque (FR-010 violates "inspectable").
- TOML. Rejected: heavier parser (stdlib only since 3.11; still
  fine, but JSON is simpler for a nested map shape).
- One file per year. Rejected: see above.
- SQLite. Rejected: massive overkill for ~10 rows per year.

---

## 4. Atomic write and concurrent-write safety

**Decision**: Write to a sibling temp file in the same directory,
flush + fsync, then `os.replace()` over the destination. On
read, treat any JSON parse failure as a cache miss (refetch).
No `fcntl` / `msvcrt` locking — last-writer-wins is acceptable
because both writers serialize structurally valid content for
the same (region, year) (FR-013).

```python
def _save_cache(cache: dict, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
```

**Rationale**:

- `os.replace()` is **atomic on both POSIX and Windows** when source
  and target are on the same filesystem (which they are — same dir).
- `fsync` before rename guarantees the on-disk content is durable.
- **No locking** — the cost (cross-platform `fcntl` vs `msvcrt`)
  exceeds the benefit (~10ms shaved off the rare two-writers case).
  Concurrent writers either land identical content (no harm) or
  land different content for the same year (in which case the loser
  re-fetches next run — also no harm).

**Alternatives considered**:

- `fcntl.flock` write-lock. Rejected: not portable to Windows
  without a `msvcrt.locking` branch; adds complexity for no
  user-visible benefit.
- `tempfile.NamedTemporaryFile(delete=False)`. Rejected: lands the
  temp file in `/tmp` which may be on a different filesystem
  (breaks `os.replace` atomicity).

---

## 5. Retry policy implementation shape

**Decision**: One shared loop in `holidays.py` that handles every
failure mode uniformly per FR-017. Pseudocode:

```python
def _fetch_with_retry(year: int) -> list[Holiday]:
    BUDGET_S = 5.0
    PER_ATTEMPT_TIMEOUT_S = 1.5
    BACKOFFS_S = [0.0, 0.2, 0.6]   # before attempts 1, 2, 3

    start = time.monotonic()
    last_error = None
    for attempt_index, backoff in enumerate(BACKOFFS_S):
        if backoff:
            time.sleep(backoff)
        if time.monotonic() - start >= BUDGET_S:
            break
        try:
            r = _session.get(
                f"https://date.nager.at/api/v3/PublicHolidays/{year}/DE",
                timeout=PER_ATTEMPT_TIMEOUT_S,
            )
            r.raise_for_status()
            return _validate_response(r.json(), year)  # may raise on FR-016 miss
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            continue
    raise HolidayFetchError(str(last_error) if last_error else "no attempt completed")
```

`HolidayFetchError` is a **module-private** exception caught
immediately at the call site in `holidays.get_hamburg_holidays`,
which translates it to "return an empty catalogue" — i.e. the
FR-007 fallback. The exception never propagates to the CLI; it is
not added to `errors.py`.

**Rationale**:

- **One loop = one place to test** the retry semantics (Constitution
  §IV).
- **`requests.RequestException`** covers connection errors, timeouts,
  and non-2xx via `raise_for_status` — one catch covers them all,
  matching the Q3 "retry on any failure" decision.
- **`ValueError`** covers JSON parse failures (`response.json()`
  raises it) and structural-validation failures (`_validate_response`
  raises it) — also matches Q3.
- **`time.monotonic()`** budget check is **before** each attempt's
  network call — guarantees we never block past ~5 s even if an
  attempt's timeout is misconfigured by the OS.
- **No `urllib3.Retry`** — that adapter retries by re-issuing the
  underlying request, but its budget semantics are awkward (retries
  outside our 5 s ceiling). A hand-rolled loop is clearer.

**Alternatives considered**:

- `urllib3.Retry` mounted on a `requests.adapters.HTTPAdapter`.
  Rejected as above.
- `backoff` library (PyPI). Rejected: new top-level dep, overkill
  for three attempts.
- Async/`asyncio`. Rejected: this CLI is synchronous everywhere
  else (Constitution §V — modularity / consistency).

---

## 6. Source-response validation (FR-016)

**Decision**: `_validate_response(payload, year)` does exactly:

1. **Parse-shape check**: `payload` MUST be a `list`. Each element
   MUST be a `dict` with `"date"` and `"localName"` (or `"name"`)
   strings. Anything else raises `ValueError`.
2. **Year check**: every `"date"` MUST parse as `YYYY-MM-DD` AND
   the year part MUST equal the requested `year`. Off-year dates
   raise `ValueError`.
3. **No count check**, **no name cross-check** — per Q2 decision,
   trust the source on which Hamburg holidays exist.
4. **Hamburg filter**: keep entries whose `counties` is `null` (=
   federal, applies to Hamburg) or whose `counties` array contains
   `"DE-HH"`. Drop everything else (e.g., entries `counties` ==
   `["DE-BY"]` are Bavaria-only).

A successful validation returns `list[Holiday]` (the in-memory
shape, see `data-model.md`).

**Rationale**: maps directly to the spec Q2 clarification — the
narrowest validation that still rejects genuinely-corrupted
responses, without encoding Hamburg-specific knowledge in the
validator.

**Alternatives considered**:

- Pydantic. Rejected: new top-level dep for a 5-field shape.
- `dataclasses.dataclass(frozen=True)` + manual `from_dict` factory.
  Adopted (see `data-model.md`) but the validator itself is just a
  function, not a model.

---

## 7. Where the fetch is triggered in the CLI flow

**Decision**: `cli._run` calls `holidays.get_hamburg_holidays(year)`
**before** `build_planned_entries`, after the project / task pickers
but before the activity-summary fetch from Moco. Catalogue lookup
is passed into `build_planned_entries` so the planner can mark
holiday rows at construction time.

```python
# in cli._run, after _pick_task(project) succeeds:
weekdays = weekday_dates(year, month)
holiday_catalogue = holidays.get_hamburg_holidays(year)  # ← NEW
activities = client.get_activities(...)
entries = build_planned_entries(year, month, activities, holiday_catalogue)
```

**Rationale**:

- The status line (FR-015) fires from inside `get_hamburg_holidays`
  only when a cold-cache fetch is triggered. The interactive flow
  already paused for the project / task pickers, so the wait fits
  the user's expectation of "the tool is doing something before
  showing me the table".
- Passing the catalogue into the planner as an argument keeps the
  planner pure (no module-level side effect) and unit-testable.
- The catalogue is computed **once per run** — even if the user
  bounces between days in the preview, the holiday map doesn't
  re-fetch.

**Alternatives considered**:

- Fetching inside `build_planned_entries`. Rejected: couples the
  planner to network / disk I/O and complicates the existing tests.
- Fetching at module import time. Rejected: every test import
  would either hit the network or need a global mock — fragile.

---

## 8. PlannedEntry model extension

**Decision**: Add one optional field to `PlannedEntry`:

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
    holiday_name: Optional[str] = None   # ← NEW
```

Semantics:

- `holiday_name is not None` ⇒ the date is a Hamburg public holiday.
- `holiday_name and already_logged` ⇒ the row is rendered as
  `already_logged` per FR-005 (the holiday name is **preserved** on
  the entry but the State column shows "already logged" not the
  holiday name).
- `holiday_name and not already_logged and not included` ⇒ the row
  is rendered in the new `row.holiday` state and the State column
  shows `holiday: Karfreitag` (FR-003, FR-004).
- `holiday_name and not already_logged and included` ⇒ the user has
  overridden the auto-skip (FR-006). The row is rendered as a normal
  `row.planned` / `row.topup` entry; the holiday name is **kept**
  on the entry so a later `Skip` action can restore the
  auto-skipped-holiday state (FR-007).

**Rationale**:

- A single optional field captures every state combination needed
  by FR-003 / FR-004 / FR-005 / FR-006 / FR-007.
- No new dataclass — extending `PlannedEntry` keeps the preview's
  one-row-one-object invariant.
- Default `None` means existing callers (and existing tests) don't
  need updates.

**Alternatives considered**:

- A separate `HolidayMetadata` wrapper around `PlannedEntry`.
  Rejected: doubles the row's identity and breaks the planner's
  "one PlannedEntry per weekday" invariant.
- A separate `is_holiday: bool` flag. Rejected: loses the name,
  forcing a second lookup at render time.

---

## 9. Row state derivation (extension of feature 002's table)

**Decision**: Extend the four-state table in feature 002's
`data-model.md` § `RowPresentation` with a fifth state:

| `PlannedEntry` condition | `style_class` | State-column label |
|--------------------------|---------------|--------------------|
| `already_logged == True` | `row.locked` | `[already logged]` |
| `holiday_name is not None and not included and not already_logged` | `row.holiday` | `[holiday: <name>]` |
| `included == False` (and not locked, not holiday-auto-skipped) | `row.skipped` | `[skipped]` |
| `included == True and existing_hours_total > 0` | `row.topup` | `[top-up: existing <h>h]` |
| `included == True and existing_hours_total == 0` | `row.planned` | (no trailing label) |

The five conditions are mutually exclusive and exhaustive given the
combinations of `holiday_name`, `already_logged`, and `included`.

**Rationale**: keeps the dispatch a flat five-arm conditional;
matches the feature 002 pattern of "state derived from entry, no
external state".

**Alternatives considered**:

- A separate "holiday-but-overridden" state. Rejected: when the
  user re-includes a holiday row, the State column should look
  exactly like a normal `row.planned` / `row.topup` row (FR-006);
  no new style class is needed because the row IS a normal
  included row at that point.

---

## 10. Styling palette extension

**Decision**: One new `row.holiday` style class in
`src/moco_filler/styling.py`'s `build_style()`:

| Class | Applied to | Suggested colour |
|-------|------------|------------------|
| `row.holiday` | a Hamburg-public-holiday auto-skipped row | bright magenta / 256 colour `#d75fd7` |

Reasoning for **magenta**: it is the only ANSI 8-colour primary not
yet used by the existing palette (cyan / yellow / dim-grey / dim-red
/ bright-green / bright-red). Choosing a fresh primary maximises
pairwise distinguishability from all existing row classes (US2 of
feature 003).

When colour is disabled, the State column's textual `[holiday:
Karfreitag]` label is what identifies the row (per Q2 of feature
003's clarifications and FR-008 of feature 004).

**Rationale**: extends feature 002's palette by **one** class, no
other class is renamed or repurposed (Constitution §II — no
ripple-effect changes).

**Alternatives considered**:

- Reusing `row.skipped` with a different label. Rejected: violates
  feature 003 US2 AC#2 — "the two rows are visually and textually
  distinguishable".
- Dim blue. Rejected: less distinguishable from cyan (`row.planned`).

---

## 11. Unit-test boundary

Per Constitution §IV, write unit tests for:

- `holidays._cache_path()` returns the expected per-OS path under
  monkeypatched `sys.platform` and env vars.
- `holidays._load_cache()` returns `None` on: missing file, parse
  failure, schema mismatch, missing region, missing year.
- `holidays._load_cache()` returns the correct in-memory shape on a
  valid file.
- `holidays._save_cache()` writes a round-trippable file and is
  atomic (assert tempfile exists during write via a fault-injected
  callback, OR more simply assert post-write file integrity).
- `holidays._validate_response()` accepts valid Nager.Date payloads,
  rejects non-list / non-dict / missing-date / off-year payloads.
- `holidays._validate_response()` correctly filters Hamburg-relevant
  entries (federal + DE-HH) and drops other-state entries.
- `holidays._fetch_with_retry()` exhausts ~5s wall-clock and 3
  attempts in the worst case, succeeds on first/second/third
  attempt as expected; budget enforcement tested with
  monkeypatched `time.monotonic`.
- `holidays.get_hamburg_holidays(year)` returns the cached
  catalogue when present, fetches + caches when absent, returns
  `{}` (FR-007 fallback) when fetch fails after retries.
- `planner.build_planned_entries(..., holiday_catalogue)` marks
  holiday weekdays as `holiday_name=<name>, included=False, hours=0`
  by default.
- `planner` honours FR-005 — when a date is both already-logged and
  a holiday, the row is `already_logged=True` AND
  `holiday_name=<name>` is preserved (no precedence drop).
- `planner.toggle_skipped(row)` on a holiday row flips to
  `included=True`, preserving `holiday_name` (US3 override).
- `models.PlannedEntry` default value of `holiday_name` is `None`.

**NOT tested**:

- The live `date.nager.at` endpoint — Constitution §IV is
  unit-only.
- The Questionary preview loop — same carve-out as feature 002.
- The actual stderr output of the FR-015 status line — that goes
  through `print(..., file=sys.stderr)`; we assert the message
  was emitted by capturing `capsys.readouterr().err`.

---

## Summary of resolved unknowns

| Question | Outcome |
|----------|---------|
| Which holiday source | `date.nager.at` (free, no auth, subdivision-aware) |
| Cache location | per-OS user cache dir, stdlib-only resolver |
| Cache file format | one JSON file, `schema_version: 1`, nested `regions.<id>.<year>` |
| Atomic-write safety | tempfile + `os.replace`, no `fcntl` |
| Retry loop shape | 3 attempts, 1.5s per-attempt, 5s total, hand-rolled |
| Source validation | structural + year only; no count or name check |
| Fetch trigger point | once per run, after task picker, before activity fetch |
| `PlannedEntry` change | one new optional field `holiday_name: Optional[str]` |
| New style class | `row.holiday` — bright magenta |
| Test surface | source/cache/retry/planner all unit-tested; no live HTTP |
