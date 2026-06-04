# Contract: On-Disk Holiday Cache File

**Feature**: 004-cache-holidays-locally (bundled with 003)

**Date**: 2026-06-04

This document specifies the **on-disk** contract for the local
holiday cache produced by `src/moco_filler/holidays.py`. It is NOT
a CLI surface and is NOT covered by the
`specs/001-create-mvp-moco-filler-app/contracts/cli.md` stdout-scrape
contract. The HTTP source response is a separate contract; see
[`holiday-source.md`](./holiday-source.md).

---

## File location

| Platform | Path |
|----------|------|
| macOS | `~/Library/Caches/moco-filler/holidays.json` |
| Linux | `${XDG_CACHE_HOME:-$HOME/.cache}/moco-filler/holidays.json` |
| Windows | `%LOCALAPPDATA%\moco-filler\Cache\holidays.json` (fallback: `~/AppData/Local/moco-filler/Cache/holidays.json`) |
| Other | `~/.cache/moco-filler/holidays.json` |

The directory is created lazily on first write (`mkdir -p` with
`exist_ok=True`). A missing directory or a directory the user can't
write to is **not** an error — the run completes without caching
(FR-006 / FR-007), and the next run on a writable filesystem will
recreate the cache.

The path is per-user; multiple users on the same machine each get
their own cache.

---

## Schema (version 1)

```jsonc
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
          {"date": "2026-05-01", "name": "Tag der Arbeit"},
          {"date": "2026-05-14", "name": "Christi Himmelfahrt"},
          {"date": "2026-05-25", "name": "Pfingstmontag"},
          {"date": "2026-10-03", "name": "Tag der Deutschen Einheit"},
          {"date": "2026-10-31", "name": "Reformationstag"},
          {"date": "2026-12-25", "name": "1. Weihnachtsfeiertag"},
          {"date": "2026-12-26", "name": "2. Weihnachtsfeiertag"}
        ]
      }
    }
  }
}
```

### Required fields

- `schema_version` (integer): MUST be exactly `1` in this version
  of the tool. Any other value (including missing) is a **cache
  miss** — the entire file is treated as if it didn't exist and a
  fresh fetch happens. This is the schema-version invalidation
  hook from spec § Edge Cases.
- `regions` (object): keys are region identifiers (currently always
  `"DE-HH"`; future regions live here too). Values are year-keyed
  objects.
- `regions.<region>.<year>` (object): the cached entry for one
  (region, year) pair. Year key MUST be a four-digit Gregorian year
  as a JSON **string** key (JSON object keys are strings; the year
  is parsed back to an int when read).
- `regions.<region>.<year>.fetched_at` (string): ISO-8601 UTC
  timestamp (`%Y-%m-%dT%H:%M:%SZ`) recording when the entry was
  fetched. Informational only — not used for cache invalidation
  (FR-011 says no auto-refresh inside a year).
- `regions.<region>.<year>.holidays` (array): the catalogue
  entries. Each element is a `{"date": "YYYY-MM-DD", "name": "..."}`
  object. Order is informational; the runtime consumes it as a
  `dict[date, str]`.

### Optional fields

None in v1. Future versions MAY add fields here, but adding any
field beyond those listed above without bumping `schema_version`
is forbidden — see "Versioning" below.

---

## Read semantics

The reader (`holidays._load_cache(path, region, year)`) returns
`None` (= cache miss) on **any** of:

- The file does not exist or cannot be opened.
- The file contents are not valid UTF-8 JSON.
- The top-level value is not an object.
- `schema_version` is missing, is not the integer `1`.
- `regions` is missing or not an object.
- `regions[region]` is missing.
- `regions[region][str(year)]` is missing.
- The inner entry is not an object, or `holidays` is missing, or
  `holidays` is not a list, or any element fails the per-entry
  shape check (object with `date: YYYY-MM-DD` and `name: non-empty
  str`).

On a successful read, the returned shape is
`list[Holiday]` (the in-memory dataclass — `data-model.md` §
`Holiday`).

### MUST NOT raise

`_load_cache` MUST NOT raise on cache miss. Any internal exception
during read MUST be caught and translated to a `None` return. This
guarantees FR-006: malformed cache never crashes the CLI.

---

## Write semantics

The writer (`holidays._save_cache(path, region, year, entries)`) MUST:

1. Compute the target path; create parent directories with
   `exist_ok=True`.
2. Open a sibling temp file `path.with_suffix(path.suffix + ".tmp")`
   for writing in UTF-8.
3. Serialize the **merged** cache — i.e., read the existing cache
   (if any) first, splice in the new `(region, year)` entry,
   serialize the merged structure. This keeps other years untouched
   (FR-012).
4. `json.dump(merged, f, indent=2, sort_keys=True)`.
5. `f.flush()` then `os.fsync(f.fileno())`.
6. `os.replace(tmp, path)` — atomic on POSIX and Windows when source
   and target are on the same filesystem.

The writer MUST NOT raise on read failure during merge: if the
existing file is unreadable, the merge starts from a fresh
`{"schema_version": 1, "regions": {}}` skeleton, effectively
"reset" of the corrupted file.

If the writer itself fails (disk full, read-only mount, permission
denied), the exception is caught at the call site
(`holidays.get_hamburg_holidays`) and the run continues with the
in-memory catalogue — i.e., **the user still sees holiday rows in
this run**, but the next run will re-fetch (Edge Case "read-only
filesystem").

---

## Concurrent-write safety

`os.replace()` is atomic; either the old file or the new file is
visible to a concurrent reader, never a partial. Two CLI runs
fetching the same year concurrently:

- Both serialize structurally-valid content.
- Both call `os.replace()`. One wins; the loser's content is
  discarded (it would have been identical-or-near-identical
  anyway).

No `fcntl.flock` / `msvcrt.locking` is used. The window between
"read existing cache" and "replace with merged" is small (single-
digit ms) and a lost write means at most one redundant re-fetch
next run — not a correctness violation.

---

## Privacy invariants (FR-009)

The cache file MUST NOT contain:

- The Moco API key (or any token / credential).
- The user's Moco user ID, project IDs, task IDs, or activity
  records.
- The hostname of the Moco tenant (`statista.mocoapp.com` or any
  other).
- The user's name, email, or any other PII.

It MUST contain ONLY:

- The schema version.
- Region identifiers (e.g., `"DE-HH"`).
- Calendar years and their holiday lists from the public source.
- The `fetched_at` timestamps.

A reviewer should be able to `cat ~/Library/Caches/moco-filler/holidays.json`
and see nothing more sensitive than the public German holiday calendar.

---

## Versioning

The integer `schema_version` field gates compatibility:

- A reader that encounters `schema_version != <my version>` MUST
  treat the entire file as a cache miss.
- A writer MUST write `schema_version: 1` in this version of the
  tool.
- A future change that adds a field, drops a field, or changes a
  field's semantics MUST bump `schema_version` to `2` (or higher).
  Old caches are then invalidated automatically.

This means user-visible "upgrade" friction is one redundant
fetch — equivalent to deleting the cache and re-running. There is
no in-place migration in v1.

---

## What this contract does NOT promise

- **Stable on-disk ordering of keys / array elements**. The
  `sort_keys=True` flag in `json.dump` gives lexicographic
  stability, but no commitment is made to ordering of `holidays`
  array elements (Nager's order is preserved on first write; a
  re-fetch may reorder).
- **A specific compression or encoding**. Plain UTF-8, plain JSON,
  no gzip, no base64.
- **A specific filename** beyond `holidays.json`. The cache
  directory may contain additional files (e.g., `.tmp` during
  writes); only `holidays.json` is the authoritative cache.
