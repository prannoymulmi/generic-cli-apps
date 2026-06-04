# Contract: Holiday Source Response

**Feature**: 004-cache-holidays-locally (bundled with 003)

**Date**: 2026-06-04

This document specifies the **external** contract between
`src/moco_filler/holidays.py` and the public Nager.Date endpoint
that serves Hamburg holiday data. It is NOT a CLI surface — the
public CLI contract from
`specs/001-create-mvp-moco-filler-app/contracts/cli.md` is unchanged
by this feature.

The cache file format is a separate contract; see
[`holiday-cache.md`](./holiday-cache.md).

---

## Endpoint

```
GET https://date.nager.at/api/v3/PublicHolidays/{year}/DE
```

| Param | Type | Constraint |
|-------|------|------------|
| `{year}` | integer | Four-digit Gregorian year of the month being previewed (`cli.parse_month`'s `year`). |

**Headers**: `Accept: application/json`. No auth header. The Moco
`Authorization` header is **not** sent — the Nager.Date source MUST
NOT see the user's API key.

**Timeout**: 1.5 s per attempt (`research.md` §5).

**Retries**: 3 attempts max within a 5 s wall-clock budget per
FR-017. Backoffs ~0 ms / ~200 ms / ~600 ms before attempts 1 / 2 / 3.

---

## Response shape we depend on

```jsonc
[
  {
    "date": "2026-04-03",          // REQUIRED — YYYY-MM-DD
    "localName": "Karfreitag",     // REQUIRED — German name
    "name": "Good Friday",         // OPTIONAL — English name, we ignore it
    "countryCode": "DE",           // OPTIONAL — we ignore it
    "fixed": false,                // OPTIONAL — we ignore it
    "global": true,                // OPTIONAL — we ignore it
    "counties": null,              // OPTIONAL — null = federal (includes Hamburg)
    "launchYear": null,            // OPTIONAL — we ignore it
    "types": ["Public"]            // OPTIONAL — we ignore it
  },
  {
    "date": "2026-10-31",
    "localName": "Reformationstag",
    "counties": ["DE-BB", "DE-HB", "DE-HH", "DE-MV", "DE-NI",
                 "DE-SN", "DE-ST", "DE-SH", "DE-TH"]  // Hamburg-applicable
  },
  {
    "date": "2026-08-15",
    "localName": "Mariä Himmelfahrt",
    "counties": ["DE-BY", "DE-SL"]   // Bavaria + Saarland — NOT Hamburg
  }
]
```

### Required fields per entry

- `date`: string, `YYYY-MM-DD`. MUST parse as a real date in the
  requested year. If it fails to parse OR is in a different year,
  the entire response is rejected (treated as a failed attempt by
  the retry loop).
- `localName`: string, non-empty. This is the German name stored in
  `Holiday.name` and rendered in the State column of the preview.
  If the source ever drops `localName`, the validator falls back to
  `name`; if both are missing, the entry is rejected.

### Hamburg-applicability filter

An entry is kept iff one of:

- `counties` is missing OR `null` (federal, applies to all states), OR
- `counties` is a list of strings containing `"DE-HH"`.

All other entries are dropped silently (e.g., Mariä Himmelfahrt is
Bavaria/Saarland-only and disappears from our catalogue).

---

## What this contract does NOT promise

- **A specific count of holidays per year**. Hamburg currently has
  ~10 public holidays; future law changes may add or remove some.
  The validator imposes no count envelope (Q2 clarification —
  trust the source on this).
- **A specific name spelling**. If Nager renames `Karfreitag` to
  `Karfreitag (Good Friday)` or similar, the State column reflects
  that. We MUST NOT post-process the name.
- **A stable response ordering**. The validator preserves whatever
  order Nager returns, but the planner consumes a `dict[date, str]`
  so the order is irrelevant at runtime.
- **Live-source availability**. If the endpoint is unreachable,
  slow, or returns malformed data on every attempt, the tool
  degrades per FR-007 to the unknown-year behaviour (empty
  catalogue, no holiday rows marked). The retry loop is the only
  resilience surface.

---

## What the tool MUST NOT do with the response

- MUST NOT log or echo the raw response to stdout / stderr. The
  FR-015 status message is a single fixed sentence; no payload data
  leaks into the user-visible output.
- MUST NOT cache the unfiltered response. Only the Hamburg-relevant
  subset is written to `holidays.json` (FR-009: cache contains
  only what the tool needs).
- MUST NOT make multiple parallel requests for the same year on the
  same run. One request per cold-cache fetch.

---

## Versioning

The endpoint version is encoded in the URL path (`/api/v3/`).
If Nager publishes a `v4` that's incompatible with this contract,
the implementation bumps the URL and the cache schema version in
lockstep (`holiday-cache.md`).

The current contract targets `v3` as of 2026-06-04.
