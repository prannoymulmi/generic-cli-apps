"""Hamburg public-holiday catalogue with on-disk caching.

Owns the source-fetch + local-cache lifecycle for the holiday list
``planner.py`` consumes when building rows. Implements every
behavioural requirement from
``specs/004-cache-holidays-locally/spec.md`` and
``specs/003-hamburg-holidays-skip/spec.md``:

- Fetch once per (region, year) from ``date.nager.at`` and persist to
  a per-user JSON cache; subsequent runs read from cache and never
  re-query (FR-001..FR-004, FR-011).
- Stdlib-only per-OS cache directory resolver — no
  ``platformdirs`` dependency (FR-005, FR-010).
- Atomic-rename writes so concurrent CLI invocations cannot corrupt
  the cache (FR-013).
- Light structural validation: parse-shape check + year check +
  Hamburg-applicability filter; no count envelope, no
  cross-check against a hard-coded Hamburg catalogue (FR-016, Q2).
- Three-attempt retry loop with ~1.5 s per-attempt timeout and ~5 s
  total wall-clock budget, then graceful degrade to the empty
  catalogue (FR-007, FR-008, FR-017, Q3).
- Single-line stderr status message on cold-cache fetch so the
  ≤ 5 s wait does not feel like a freeze (FR-015).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


# ---- on-disk shape ------------------------------------------------------

CACHE_SCHEMA_VERSION = 1
REGION_HAMBURG = "DE-HH"
_CACHE_DIR_NAME = "moco-filler"
_CACHE_FILE_NAME = "holidays.json"

# ---- network shape ------------------------------------------------------

_SOURCE_URL_TEMPLATE = "https://date.nager.at/api/v3/PublicHolidays/{year}/DE"
_PER_ATTEMPT_TIMEOUT_S = 1.5
_TOTAL_BUDGET_S = 5.0
_BACKOFFS_S = (0.0, 0.2, 0.6)  # before attempts 1, 2, 3


@dataclass(frozen=True)
class Holiday:
    """One Hamburg public holiday in the requested year.

    Built by :func:`_validate_response` after filtering the Nager.Date
    payload to Hamburg-applicable entries. Frozen so the catalogue is
    safe to hand off by reference.
    """

    date: date
    name: str


class HolidayFetchError(Exception):
    """Internal: every attempt in the retry loop failed.

    Caught at the boundary in :func:`get_hamburg_holidays` and
    translated to the FR-007 empty-catalogue fallback. NOT added to
    ``errors.py`` because the CLI never sees this — the public API
    swallows it.
    """


# ---- cache-path resolver (research.md §2) -------------------------------


def _cache_path() -> Path:
    """Return the per-user cache file path for the host OS.

    Stdlib-only — no ``platformdirs`` dependency (FR-010). One file
    holds all (region, year) entries; the directory is created lazily
    on first write.
    """
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    elif sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        base = (
            Path(local) if local else Path.home() / "AppData" / "Local"
        )
        return base / _CACHE_DIR_NAME / "Cache" / _CACHE_FILE_NAME
    elif sys.platform.startswith("linux"):
        xdg = os.environ.get("XDG_CACHE_HOME", "").strip()
        base = Path(xdg) if xdg else Path.home() / ".cache"
    else:
        base = Path.home() / ".cache"
    return base / _CACHE_DIR_NAME / _CACHE_FILE_NAME


# ---- cache I/O (contracts/holiday-cache.md) -----------------------------


def _read_cache_file(path: Path) -> Optional[Dict[str, Any]]:
    """Parse the cache file. Returns ``None`` on ANY failure.

    No exception ever escapes — the contract guarantees a malformed
    cache never crashes the CLI (FR-006).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("schema_version") != CACHE_SCHEMA_VERSION:
        return None
    if not isinstance(data.get("regions"), dict):
        return None
    return data


def _load_cache(
    path: Path, region: str, year: int
) -> Optional[List[Holiday]]:
    """Return the cached catalogue for ``(region, year)``, or ``None``.

    A ``None`` return means cache miss — file missing, malformed JSON,
    wrong schema version, missing region, missing year, or malformed
    inner entries. Never raises.
    """
    data = _read_cache_file(path)
    if data is None:
        return None
    region_block = data["regions"].get(region)
    if not isinstance(region_block, dict):
        return None
    year_block = region_block.get(str(year))
    if not isinstance(year_block, dict):
        return None
    entries = year_block.get("holidays")
    if not isinstance(entries, list):
        return None
    parsed: List[Holiday] = []
    for raw in entries:
        if not isinstance(raw, dict):
            return None
        d = _parse_iso_date(raw.get("date"))
        name = raw.get("name")
        if d is None or not isinstance(name, str) or not name:
            return None
        parsed.append(Holiday(date=d, name=name))
    return parsed


def _save_cache(
    path: Path, region: str, year: int, entries: List[Holiday]
) -> None:
    """Merge ``entries`` into the cache under ``(region, year)``.

    Atomic write: serialise to a sibling temp file, ``fsync``, then
    ``os.replace``. Other years inside the same file are preserved
    (FR-012). The write raises on filesystem failure (permission
    denied, disk full); the call site in :func:`get_hamburg_holidays`
    catches and treats that as a save-failure (run continues, next
    run re-fetches).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_cache_file(path) or {
        "schema_version": CACHE_SCHEMA_VERSION,
        "regions": {},
    }
    existing.setdefault("schema_version", CACHE_SCHEMA_VERSION)
    existing.setdefault("regions", {})
    existing["regions"].setdefault(region, {})
    existing["regions"][region][str(year)] = {
        "fetched_at": _now_utc_iso(),
        "holidays": [
            {"date": h.date.isoformat(), "name": h.name}
            for h in entries
        ],
    }
    # Atomic write via tempfile + os.replace in the same directory.
    fd, tmp_path = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---- response validation (research.md §6, FR-016) -----------------------


def _validate_response(payload: Any, year: int) -> List[Holiday]:
    """Parse the source's JSON payload into the Hamburg-applicable list.

    Per FR-016 (Q2 clarification): structural check + year check;
    no count envelope, no cross-check against expected names. Raises
    ``ValueError`` on any failure — the retry loop treats that as a
    failed attempt.
    """
    if not isinstance(payload, list):
        raise ValueError("source payload is not a list")
    result: List[Holiday] = []
    for raw in payload:
        if not isinstance(raw, dict):
            raise ValueError("source entry is not an object")
        d = _parse_iso_date(raw.get("date"))
        if d is None:
            raise ValueError("source entry has missing or invalid date")
        if d.year != year:
            raise ValueError(
                f"source entry date {d.isoformat()} is not in year {year}"
            )
        name_value = raw.get("localName") or raw.get("name")
        if not isinstance(name_value, str) or not name_value:
            raise ValueError("source entry has missing or empty name")
        if not _is_hamburg_applicable(raw.get("counties")):
            continue
        result.append(Holiday(date=d, name=name_value))
    return result


def _is_hamburg_applicable(counties: Any) -> bool:
    """Federal entry (``counties is None``) OR list containing ``DE-HH``."""
    if counties is None:
        return True
    if isinstance(counties, list):
        return REGION_HAMBURG in counties
    return False


# ---- retry loop (research.md §5, FR-008 + FR-017) -----------------------


def _fetch_with_retry(
    year: int,
    session: Optional[requests.Session] = None,
    now: Any = time.monotonic,
    sleep: Any = time.sleep,
) -> List[Holiday]:
    """Three-attempt fetch with ~1.5 s per attempt + ~5 s total budget.

    ``session``, ``now``, and ``sleep`` are injectable so tests can
    exercise the retry / budget semantics without touching the
    network or the real clock. Raises :class:`HolidayFetchError`
    when no attempt succeeds inside the budget.
    """
    if session is None:
        session = requests.Session()
    url = _SOURCE_URL_TEMPLATE.format(year=year)
    start = now()
    last_error: Optional[Exception] = None
    for backoff in _BACKOFFS_S:
        if backoff:
            sleep(backoff)
        if now() - start >= _TOTAL_BUDGET_S:
            break
        try:
            response = session.get(
                url,
                timeout=_PER_ATTEMPT_TIMEOUT_S,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return _validate_response(response.json(), year)
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            continue
    raise HolidayFetchError(
        str(last_error) if last_error else "no fetch attempt completed"
    )


# ---- public catalogue accessor ------------------------------------------


def get_hamburg_holidays(year: int) -> Dict[date, str]:
    """Return ``{date → German holiday name}`` for Hamburg in ``year``.

    Reads the local cache first. On miss, prints the FR-015 status
    line to stderr, fetches with retry, and writes the cache. On
    irrecoverable failure (all retries exhausted), returns ``{}`` so
    the CLI degrades to the FR-007 unknown-year fallback (no holiday
    rows marked, no error message).
    """
    path = _cache_path()
    cached = _load_cache(path, REGION_HAMBURG, year)
    if cached is not None:
        return {h.date: h.name for h in cached}

    print(
        f"Fetching Hamburg public holidays for {year}…",
        file=sys.stderr,
    )
    try:
        entries = _fetch_with_retry(year)
    except HolidayFetchError:
        return {}
    try:
        _save_cache(path, REGION_HAMBURG, year, entries)
    except OSError:
        # Save failure (read-only FS, permission denied) is not fatal
        # — the in-memory catalogue is still usable for this run.
        pass
    return {h.date: h.name for h in entries}


# ---- helpers ------------------------------------------------------------


def _parse_iso_date(raw: Any) -> Optional[date]:
    if not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _now_utc_iso() -> str:
    return (
        datetime.now(tz=timezone.utc)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )
