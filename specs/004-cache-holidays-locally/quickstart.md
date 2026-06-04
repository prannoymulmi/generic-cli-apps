# Quickstart: Working with the Hamburg Holiday Cache

**Feature**: 004-cache-holidays-locally (bundled with 003)

**Date**: 2026-06-04

This document is the developer / power-user quickstart for the
new holiday-caching behaviour. The user-visible behaviour is
described in `spec.md` § User Scenarios.

---

## TL;DR

- The first time you run `moco-filler` for a given year, the tool
  fetches that year's Hamburg public holidays from
  `date.nager.at` and writes them to a JSON cache in your
  per-OS cache directory.
- Every subsequent run for any month in that year reads from the
  cache. **Zero network calls** for holiday data on a cache hit.
- To force a re-fetch, delete the cache file (or just the year
  entry inside it).
- Offline? If a cache for the year exists, you'll see holidays
  normally. If not, the tool degrades silently to "no holidays
  marked" (FR-007) and you can still book hours as usual.

---

## Where is the cache?

| Platform | Path |
|----------|------|
| macOS | `~/Library/Caches/moco-filler/holidays.json` |
| Linux | `${XDG_CACHE_HOME:-$HOME/.cache}/moco-filler/holidays.json` |
| Windows | `%LOCALAPPDATA%\moco-filler\Cache\holidays.json` |

The file is plain JSON, human-readable, and safe to `cat` — it
contains only the public German holiday calendar, never any
Moco credentials or project data (see
[`contracts/holiday-cache.md`](./contracts/holiday-cache.md) §
Privacy invariants).

---

## Inspecting the cache

```bash
# macOS / Linux
cat "${XDG_CACHE_HOME:-$HOME/.cache}/moco-filler/holidays.json" | jq

# macOS-only shortcut
cat ~/Library/Caches/moco-filler/holidays.json | jq
```

You should see a top-level `{"schema_version": 1, "regions": {"DE-HH": ...}}`
shape. Each inner year entry has a `fetched_at` ISO-8601 timestamp
and a `holidays` array of `{"date": ..., "name": ...}` pairs.

---

## Forcing a refresh

There is no `--refresh-holidays` flag in v1 (intentional; see
spec § Assumptions). To force a re-fetch:

```bash
# Refresh everything
rm "${XDG_CACHE_HOME:-$HOME/.cache}/moco-filler/holidays.json"   # Linux/macOS
rm "$HOME/Library/Caches/moco-filler/holidays.json"              # macOS-only shortcut

# Refresh just one year (requires jq)
jq 'del(.regions["DE-HH"]["2026"])' holidays.json > holidays.json.new \
  && mv holidays.json.new holidays.json
```

The next `moco-filler` run that needs a deleted entry will fetch
it from `date.nager.at` again and re-populate the cache.

---

## Running offline

- **Cache populated for the requested year** → preview works
  normally; holidays are auto-skipped and labelled.
- **No cache for the requested year, and you're offline** → the
  tool degrades silently after the FR-017 retry path exhausts (no
  holiday rows marked, no error message, exit code unchanged).
  You can still book hours; just verify by hand that you're not
  scheduling onto a Hamburg public holiday.

---

## The first-run wait

When a cold-cache fetch fires, you'll see a single line on stderr
before the preview opens:

```
Fetching Hamburg public holidays for 2026…
```

This is FR-015. The wait is bounded at ~5 s wall-clock in the
worst case (three failed attempts at ~1.5 s each with backoffs).
A healthy network path completes the first attempt in well under
1 second.

The stdout-scrape contract from feature 001 is **not** affected —
the status line goes to **stderr** only. Tools that pipe stdout
through `grep "^Created"` still work identically.

---

## Verifying behaviour locally

Manual end-to-end check (no automated test for the live source —
Constitution §IV):

```bash
# 1. Cold-cache run: should see the stderr status line and create the cache file
rm -f ~/Library/Caches/moco-filler/holidays.json
moco-filler --month 2026-05

# 2. Warm-cache run: should be silent on stderr and skip the network entirely
moco-filler --month 2026-05 2>&1 | grep "Fetching" && echo "FAIL: refetched" || echo "OK: cache hit"
```

For the test suite (`tests/test_holidays.py`), the network is
**always** stubbed via an injected fake `requests.Session`. No
live HTTP request is ever made from the test suite.

---

## What to do when Hamburg changes its holiday law

The catalogue is fetched fresh once per (region, year). When a law
change takes effect for a future year, the next first-run for that
year picks up the new list automatically. No code change in
`moco-filler` is required.

Within an already-cached year, the cache holds the pre-amendment
list until the user deletes the file (Edge Case in spec.md). This
is the accepted limitation; in practice Hamburg's holiday law
changes are rare (the last one — Reformationstag from 2018 — was
the first in ~50 years).

---

## What the implementation surfaces (developer reference)

```python
# Public API of src/moco_filler/holidays.py
def get_hamburg_holidays(year: int) -> dict[date, str]:
    """Return {date → German holiday name} for `year`. Empty dict on degrade."""

# Used by planner.build_planned_entries — pass the result through
# as the `holiday_catalogue` argument and the planner takes it from there.
```

Module-private helpers (`_cache_path`, `_load_cache`, `_save_cache`,
`_fetch_with_retry`, `_validate_response`) are unit-tested directly.
The live HTTP boundary is the only thing that is **not** unit-
tested (per Constitution §IV — unit tests only, no live network).

For full design rationale, see
[`research.md`](./research.md) and
[`data-model.md`](./data-model.md).
