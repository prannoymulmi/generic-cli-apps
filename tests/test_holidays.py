"""Unit tests for moco_filler.holidays — cache I/O, validator, retry loop.

Per Constitution §IV (Unit Tests Only), the live ``date.nager.at``
endpoint is never contacted. Every fetch-path test injects a fake
``Session`` whose ``.get()`` returns canned ``Response``-shaped
objects, and ``time.monotonic`` / ``time.sleep`` are injected too
so the retry / budget semantics run instantly.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import pytest
import requests

from moco_filler import holidays
from moco_filler.holidays import (
    CACHE_SCHEMA_VERSION,
    REGION_HAMBURG,
    Holiday,
    HolidayFetchError,
    _cache_path,
    _fetch_with_retry,
    _load_cache,
    _save_cache,
    _validate_response,
    get_hamburg_holidays,
)


# ---------- helpers ----------


class _FakeResponse:
    """Minimal stand-in for ``requests.Response``."""

    def __init__(
        self,
        *,
        status_code: int = 200,
        payload: Any = None,
        raises_on_json: bool = False,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self._raises_on_json = raises_on_json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        if self._raises_on_json:
            raise ValueError("malformed JSON")
        return self._payload


class _FakeSession:
    """Returns canned responses in order; raises after the last one."""

    def __init__(self, responses: Iterable[Any]) -> None:
        self._responses: List[Any] = list(responses)
        self.calls: List[str] = []

    def get(self, url: str, **kwargs: Any) -> Any:
        self.calls.append(url)
        if not self._responses:
            raise AssertionError("no more canned responses")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _hamburg_sample(year: int) -> List[Dict[str, Any]]:
    """Minimal Nager-shaped payload for ``year`` with two Hamburg holidays."""
    return [
        {
            "date": f"{year}-01-01",
            "localName": "Neujahrstag",
            "name": "New Year's Day",
            "counties": None,
        },
        {
            "date": f"{year}-05-01",
            "localName": "Tag der Arbeit",
            "name": "Labour Day",
            "counties": None,
        },
        {
            "date": f"{year}-10-31",
            "localName": "Reformationstag",
            "name": "Reformation Day",
            "counties": ["DE-BB", "DE-HB", "DE-HH", "DE-NI"],
        },
        {
            "date": f"{year}-08-15",
            "localName": "Mariä Himmelfahrt",
            "name": "Assumption Day",
            "counties": ["DE-BY", "DE-SL"],  # NOT Hamburg
        },
    ]


# ---------- T002: _cache_path() per-OS ----------


def test_cache_path_on_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("moco_filler.holidays.sys.platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/Users/u")))
    assert _cache_path() == Path(
        "/Users/u/Library/Caches/moco-filler/holidays.json"
    )


def test_cache_path_on_linux_with_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("moco_filler.holidays.sys.platform", "linux")
    monkeypatch.setenv("XDG_CACHE_HOME", "/tmp/xdg-cache")
    assert _cache_path() == Path("/tmp/xdg-cache/moco-filler/holidays.json")


def test_cache_path_on_linux_without_xdg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("moco_filler.holidays.sys.platform", "linux")
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/u")))
    assert _cache_path() == Path("/home/u/.cache/moco-filler/holidays.json")


def test_cache_path_on_linux_with_empty_xdg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty XDG_CACHE_HOME is treated as unset."""
    monkeypatch.setattr("moco_filler.holidays.sys.platform", "linux")
    monkeypatch.setenv("XDG_CACHE_HOME", "")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/u")))
    assert _cache_path() == Path("/home/u/.cache/moco-filler/holidays.json")


def test_cache_path_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("moco_filler.holidays.sys.platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", "C:\\Users\\u\\AppData\\Local")
    expected = (
        Path("C:\\Users\\u\\AppData\\Local")
        / "moco-filler"
        / "Cache"
        / "holidays.json"
    )
    assert _cache_path() == expected


def test_cache_path_unknown_platform_falls_back_to_dot_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("moco_filler.holidays.sys.platform", "freebsd13")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/u")))
    assert _cache_path() == Path("/home/u/.cache/moco-filler/holidays.json")


# ---------- T003: _load_cache() miss modes ----------


def test_load_cache_returns_none_when_file_missing(tmp_path: Path) -> None:
    assert _load_cache(tmp_path / "nope.json", REGION_HAMBURG, 2026) is None


def test_load_cache_returns_none_on_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "holidays.json"
    path.write_text("{ not valid json", encoding="utf-8")
    assert _load_cache(path, REGION_HAMBURG, 2026) is None


def test_load_cache_returns_none_on_missing_schema_version(
    tmp_path: Path,
) -> None:
    path = tmp_path / "holidays.json"
    path.write_text(json.dumps({"regions": {}}), encoding="utf-8")
    assert _load_cache(path, REGION_HAMBURG, 2026) is None


def test_load_cache_returns_none_on_wrong_schema_version(
    tmp_path: Path,
) -> None:
    path = tmp_path / "holidays.json"
    path.write_text(
        json.dumps({"schema_version": 99, "regions": {}}),
        encoding="utf-8",
    )
    assert _load_cache(path, REGION_HAMBURG, 2026) is None


def test_load_cache_returns_none_on_missing_region(tmp_path: Path) -> None:
    path = tmp_path / "holidays.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": CACHE_SCHEMA_VERSION,
                "regions": {"DE-BY": {"2026": {"holidays": []}}},
            }
        ),
        encoding="utf-8",
    )
    assert _load_cache(path, REGION_HAMBURG, 2026) is None


def test_load_cache_returns_none_on_missing_year(tmp_path: Path) -> None:
    path = tmp_path / "holidays.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": CACHE_SCHEMA_VERSION,
                "regions": {REGION_HAMBURG: {"2025": {"holidays": []}}},
            }
        ),
        encoding="utf-8",
    )
    assert _load_cache(path, REGION_HAMBURG, 2026) is None


def test_load_cache_returns_none_on_malformed_entries(tmp_path: Path) -> None:
    path = tmp_path / "holidays.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": CACHE_SCHEMA_VERSION,
                "regions": {
                    REGION_HAMBURG: {
                        "2026": {
                            "holidays": [{"date": "not-a-date", "name": "x"}]
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    assert _load_cache(path, REGION_HAMBURG, 2026) is None


def test_load_cache_happy_path_returns_holidays(tmp_path: Path) -> None:
    path = tmp_path / "holidays.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": CACHE_SCHEMA_VERSION,
                "regions": {
                    REGION_HAMBURG: {
                        "2026": {
                            "fetched_at": "2026-06-04T11:42:17Z",
                            "holidays": [
                                {"date": "2026-01-01", "name": "Neujahrstag"},
                                {"date": "2026-05-01", "name": "Tag der Arbeit"},
                            ],
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    result = _load_cache(path, REGION_HAMBURG, 2026)
    assert result == [
        Holiday(date=date(2026, 1, 1), name="Neujahrstag"),
        Holiday(date=date(2026, 5, 1), name="Tag der Arbeit"),
    ]


# ---------- T004: _save_cache() round-trip + merge ----------


def test_save_cache_writes_a_round_trippable_file(tmp_path: Path) -> None:
    path = tmp_path / "subdir" / "holidays.json"
    entries = [
        Holiday(date=date(2026, 1, 1), name="Neujahrstag"),
        Holiday(date=date(2026, 12, 25), name="1. Weihnachtsfeiertag"),
    ]
    _save_cache(path, REGION_HAMBURG, 2026, entries)
    # Directory was created.
    assert path.exists()
    # File round-trips.
    assert _load_cache(path, REGION_HAMBURG, 2026) == entries


def test_save_cache_preserves_other_years_inside_the_file(
    tmp_path: Path,
) -> None:
    """FR-012: writing 2027 must not drop 2026."""
    path = tmp_path / "holidays.json"
    _save_cache(
        path,
        REGION_HAMBURG,
        2026,
        [Holiday(date=date(2026, 1, 1), name="Neujahrstag")],
    )
    _save_cache(
        path,
        REGION_HAMBURG,
        2027,
        [Holiday(date=date(2027, 1, 1), name="Neujahrstag")],
    )
    assert _load_cache(path, REGION_HAMBURG, 2026) == [
        Holiday(date=date(2026, 1, 1), name="Neujahrstag")
    ]
    assert _load_cache(path, REGION_HAMBURG, 2027) == [
        Holiday(date=date(2027, 1, 1), name="Neujahrstag")
    ]


def test_save_cache_overwrites_same_year_idempotently(tmp_path: Path) -> None:
    path = tmp_path / "holidays.json"
    first = [Holiday(date=date(2026, 1, 1), name="Neujahrstag")]
    second = [
        Holiday(date=date(2026, 1, 1), name="Neujahrstag"),
        Holiday(date=date(2026, 5, 1), name="Tag der Arbeit"),
    ]
    _save_cache(path, REGION_HAMBURG, 2026, first)
    _save_cache(path, REGION_HAMBURG, 2026, second)
    assert _load_cache(path, REGION_HAMBURG, 2026) == second


def test_save_cache_resets_from_corrupt_existing_file(
    tmp_path: Path,
) -> None:
    """A corrupt existing file is overwritten with a fresh skeleton."""
    path = tmp_path / "holidays.json"
    path.write_text("{ not valid json", encoding="utf-8")
    entries = [Holiday(date=date(2026, 1, 1), name="Neujahrstag")]
    _save_cache(path, REGION_HAMBURG, 2026, entries)
    assert _load_cache(path, REGION_HAMBURG, 2026) == entries


# ---------- T005: _validate_response() ----------


def test_validate_response_accepts_valid_hamburg_payload() -> None:
    result = _validate_response(_hamburg_sample(2026), 2026)
    # 3 Hamburg-applicable entries; Mariä Himmelfahrt (DE-BY) dropped.
    assert [h.name for h in result] == [
        "Neujahrstag",
        "Tag der Arbeit",
        "Reformationstag",
    ]


def test_validate_response_filters_other_state_holidays() -> None:
    payload = [
        {
            "date": "2026-08-15",
            "localName": "Mariä Himmelfahrt",
            "counties": ["DE-BY", "DE-SL"],
        }
    ]
    assert _validate_response(payload, 2026) == []


def test_validate_response_rejects_non_list() -> None:
    with pytest.raises(ValueError):
        _validate_response({"holidays": []}, 2026)


def test_validate_response_rejects_missing_date() -> None:
    with pytest.raises(ValueError):
        _validate_response(
            [{"localName": "Neujahrstag", "counties": None}], 2026
        )


def test_validate_response_rejects_off_year_date() -> None:
    with pytest.raises(ValueError):
        _validate_response(
            [
                {
                    "date": "2025-01-01",
                    "localName": "Neujahrstag",
                    "counties": None,
                }
            ],
            2026,
        )


def test_validate_response_accepts_name_fallback_when_localname_missing() -> None:
    """If ``localName`` is missing, ``name`` is the fallback per the contract."""
    result = _validate_response(
        [
            {
                "date": "2026-01-01",
                "name": "New Year's Day",
                "counties": None,
            }
        ],
        2026,
    )
    assert result == [Holiday(date=date(2026, 1, 1), name="New Year's Day")]


def test_validate_response_imposes_no_count_envelope() -> None:
    """Zero holidays is structurally valid (Q2 — trust the source)."""
    assert _validate_response([], 2026) == []


def test_validate_response_rejects_entry_with_blank_name() -> None:
    with pytest.raises(ValueError):
        _validate_response(
            [{"date": "2026-01-01", "localName": "", "counties": None}],
            2026,
        )


# ---------- T006: _fetch_with_retry() retry + budget semantics ----------


def _instant_clock() -> Callable[[], float]:
    """A clock that advances by 0.01 s per call so the budget check fires
    in deterministic time without actual sleeps."""
    state = {"t": 0.0}

    def now() -> float:
        state["t"] += 0.01
        return state["t"]

    return now


def test_fetch_with_retry_succeeds_on_first_attempt() -> None:
    session = _FakeSession(
        [_FakeResponse(payload=_hamburg_sample(2026))]
    )
    result = _fetch_with_retry(
        2026, session=session, now=_instant_clock(), sleep=lambda _: None
    )
    assert len(result) == 3  # Hamburg-applicable subset
    assert len(session.calls) == 1


def test_fetch_with_retry_succeeds_on_third_attempt() -> None:
    """Two transient failures, then success on attempt 3."""
    session = _FakeSession(
        [
            requests.ConnectionError("transient blip 1"),
            requests.ConnectionError("transient blip 2"),
            _FakeResponse(payload=_hamburg_sample(2026)),
        ]
    )
    result = _fetch_with_retry(
        2026, session=session, now=_instant_clock(), sleep=lambda _: None
    )
    assert len(result) == 3
    assert len(session.calls) == 3


def test_fetch_with_retry_raises_after_three_failures() -> None:
    session = _FakeSession(
        [
            requests.ConnectionError("blip 1"),
            requests.ConnectionError("blip 2"),
            requests.ConnectionError("blip 3"),
        ]
    )
    with pytest.raises(HolidayFetchError):
        _fetch_with_retry(
            2026,
            session=session,
            now=_instant_clock(),
            sleep=lambda _: None,
        )
    assert len(session.calls) == 3


def test_fetch_with_retry_propagates_validation_failure_as_retry() -> None:
    """Per Q3: parse / validation failures also feed the retry loop."""
    bad_payload = [{"date": "not-a-date", "localName": "x", "counties": None}]
    good_payload = _hamburg_sample(2026)
    session = _FakeSession(
        [
            _FakeResponse(payload=bad_payload),
            _FakeResponse(payload=good_payload),
        ]
    )
    result = _fetch_with_retry(
        2026, session=session, now=_instant_clock(), sleep=lambda _: None
    )
    assert len(result) == 3
    assert len(session.calls) == 2


def test_fetch_with_retry_aborts_when_wall_clock_budget_exhausted() -> None:
    """Budget check fires BEFORE the next attempt's network call."""
    state = {"t": 0.0}

    def slow_clock() -> float:
        state["t"] += 3.0  # each tick consumes 3 s
        return state["t"]

    # First attempt should run (t=3 < 5); second attempt shouldn't (t=6 > 5).
    session = _FakeSession(
        [
            requests.ConnectionError("blip 1"),
            # Attempt 2 should never fire — no canned response needed
        ]
    )
    with pytest.raises(HolidayFetchError):
        _fetch_with_retry(
            2026,
            session=session,
            now=slow_clock,
            sleep=lambda _: None,
        )
    assert len(session.calls) == 1


# ---------- T007: get_hamburg_holidays() orchestration ----------


@pytest.fixture
def _isolated_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Redirect _cache_path() to a tmpdir for the duration of the test."""
    cache_file = tmp_path / "holidays.json"
    monkeypatch.setattr(
        "moco_filler.holidays._cache_path", lambda: cache_file
    )
    return cache_file


def test_get_hamburg_holidays_returns_cache_on_hit(
    _isolated_cache: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Cache hit: no fetch, no status line, no Session built."""
    _save_cache(
        _isolated_cache,
        REGION_HAMBURG,
        2026,
        [Holiday(date=date(2026, 1, 1), name="Neujahrstag")],
    )

    def boom(*_a: Any, **_kw: Any) -> None:
        raise AssertionError("network must not be touched on cache hit")

    monkeypatch.setattr("moco_filler.holidays._fetch_with_retry", boom)
    result = get_hamburg_holidays(2026)
    assert result == {date(2026, 1, 1): "Neujahrstag"}
    assert "Fetching" not in capsys.readouterr().err


def test_get_hamburg_holidays_fetches_and_caches_on_miss(
    _isolated_cache: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Cache miss: fetch path runs, status line on stderr, cache written."""
    fetched = [
        Holiday(date=date(2026, 1, 1), name="Neujahrstag"),
        Holiday(date=date(2026, 5, 1), name="Tag der Arbeit"),
    ]
    monkeypatch.setattr(
        "moco_filler.holidays._fetch_with_retry",
        lambda year: fetched,
    )
    result = get_hamburg_holidays(2026)
    assert result == {
        date(2026, 1, 1): "Neujahrstag",
        date(2026, 5, 1): "Tag der Arbeit",
    }
    captured = capsys.readouterr()
    assert "Fetching Hamburg public holidays for 2026" in captured.err
    # And the cache was persisted.
    assert _load_cache(_isolated_cache, REGION_HAMBURG, 2026) == fetched


def test_get_hamburg_holidays_falls_back_to_empty_on_fetch_failure(
    _isolated_cache: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """FR-007 fallback: fetch failure returns ``{}`` and does not crash."""

    def fail(_year: int) -> None:
        raise HolidayFetchError("all three attempts failed")

    monkeypatch.setattr("moco_filler.holidays._fetch_with_retry", fail)
    result = get_hamburg_holidays(2026)
    assert result == {}
    # The status line still fired (the fetch was attempted).
    assert (
        "Fetching Hamburg public holidays for 2026"
        in capsys.readouterr().err
    )
    # And no cache was written.
    assert not _isolated_cache.exists()


def test_get_hamburg_holidays_save_failure_is_non_fatal(
    _isolated_cache: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Save failure (read-only FS) does NOT propagate."""
    fetched = [Holiday(date=date(2026, 1, 1), name="Neujahrstag")]
    monkeypatch.setattr(
        "moco_filler.holidays._fetch_with_retry",
        lambda year: fetched,
    )

    def fail_save(*_a: Any, **_kw: Any) -> None:
        raise OSError("read-only filesystem")

    monkeypatch.setattr("moco_filler.holidays._save_cache", fail_save)
    result = get_hamburg_holidays(2026)
    assert result == {date(2026, 1, 1): "Neujahrstag"}
