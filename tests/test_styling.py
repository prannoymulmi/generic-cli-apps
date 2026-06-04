"""Unit tests for moco_filler.styling — colour detection, palette, row dispatch.

Per ``specs/002-add-coloring-and-spacing-to-the-app/research.md`` §8, the live Questionary
loop is **not** unit-tested. These tests cover only the deterministic
helpers (env / TTY predicate, ``Style`` construction, FormattedText
dispatch). The actual on-terminal rendering is gated by the manual
sandbox checks in `quickstart.md` §4.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from prompt_toolkit.styles import Style

from moco_filler import styling
from moco_filler.models import PlannedEntry


# ---------- shared fixtures ----------


@pytest.fixture(autouse=True)
def _reset_style_cache() -> None:
    """Drop any cached Style between tests so each starts fresh."""
    styling._reset_cache()
    yield
    styling._reset_cache()


def _color_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force ``is_color_enabled()`` to return True for a test."""
    monkeypatch.setattr("moco_filler.styling._is_tty", lambda: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")


def _color_off_via_no_color(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("moco_filler.styling._is_tty", lambda: True)
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "xterm-256color")


def _plain_row(d: date = date(2026, 6, 3)) -> PlannedEntry:
    return PlannedEntry(
        date=d,
        weekday=d.strftime("%a"),
        existing_hours_total=Decimal("0"),
        hours=Decimal("8"),
        included=True,
        already_logged=False,
        note=None,
    )


def _top_up_row(d: date = date(2026, 6, 4)) -> PlannedEntry:
    return PlannedEntry(
        date=d,
        weekday=d.strftime("%a"),
        existing_hours_total=Decimal("4.5"),
        hours=Decimal("3.5"),
        included=True,
        already_logged=False,
        note="Top-up: existing 4.50h",
    )


def _locked_row(d: date = date(2026, 6, 5)) -> PlannedEntry:
    return PlannedEntry(
        date=d,
        weekday=d.strftime("%a"),
        existing_hours_total=Decimal("8"),
        hours=Decimal("0"),
        included=False,
        already_logged=True,
        note="Already logged (8.00h, day full)",
    )


def _skipped_row(d: date = date(2026, 6, 8)) -> PlannedEntry:
    return PlannedEntry(
        date=d,
        weekday=d.strftime("%a"),
        existing_hours_total=Decimal("0"),
        hours=Decimal("8"),
        included=False,
        already_logged=False,
        note=None,
    )


# ---------- T008: is_color_enabled() across triggers ----------


def test_is_color_enabled_when_tty_and_no_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _color_on(monkeypatch)
    assert styling.is_color_enabled() is True


def test_is_color_disabled_when_NO_COLOR_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("moco_filler.styling._is_tty", lambda: True)
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "xterm")
    assert styling.is_color_enabled() is False


def test_is_color_disabled_when_NO_COLOR_set_to_anything_nonempty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per the no-color.org convention: any non-empty value disables."""
    monkeypatch.setattr("moco_filler.styling._is_tty", lambda: True)
    monkeypatch.setenv("NO_COLOR", "yes please")
    monkeypatch.setenv("TERM", "xterm")
    assert styling.is_color_enabled() is False


def test_is_color_enabled_when_NO_COLOR_is_empty_or_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty / whitespace NO_COLOR is treated as unset."""
    monkeypatch.setattr("moco_filler.styling._is_tty", lambda: True)
    monkeypatch.setenv("NO_COLOR", "   ")
    monkeypatch.setenv("TERM", "xterm")
    assert styling.is_color_enabled() is True


def test_is_color_disabled_when_stdout_not_a_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm")
    monkeypatch.setattr("moco_filler.styling._is_tty", lambda: False)
    assert styling.is_color_enabled() is False


def test_is_color_disabled_when_TERM_is_dumb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setattr("moco_filler.styling._is_tty", lambda: True)
    assert styling.is_color_enabled() is False


# ---------- T009: build_style() returns Optional[Style] ----------


def test_build_style_returns_none_when_color_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _color_off_via_no_color(monkeypatch)
    assert styling.build_style() is None


def test_build_style_returns_style_instance_when_color_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _color_on(monkeypatch)
    style = styling.build_style()
    assert isinstance(style, Style)


def test_build_style_defines_row_palette_classes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """At minimum the four row.* classes from the contract must exist."""
    _color_on(monkeypatch)
    style = styling.build_style()
    declared_classes = {selector for selector, _ in style.style_rules}
    for cls in {"row.planned", "row.topup", "row.locked", "row.skipped"}:
        assert cls in declared_classes


def test_get_style_caches_within_one_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _color_on(monkeypatch)
    first = styling.get_style()
    second = styling.get_style()
    assert first is second


def test_get_style_returns_none_when_color_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _color_off_via_no_color(monkeypatch)
    assert styling.get_style() is None


# ---------- T010: format_styled_row dispatch ----------


def test_format_styled_row_plain_row_uses_row_planned_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _color_on(monkeypatch)
    rendered = styling.format_styled_row(_plain_row())
    assert isinstance(rendered, list)
    assert len(rendered) == 1
    assert rendered[0][0] == "class:row.planned"
    assert rendered[0][1] == "Wed  2026-06-03  8.00h  [planned]"


def test_format_styled_row_top_up_uses_row_topup_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _color_on(monkeypatch)
    rendered = styling.format_styled_row(_top_up_row(date(2026, 6, 3)))
    assert rendered[0][0] == "class:row.topup"
    assert rendered[0][1] == (
        "Wed  2026-06-03  3.50h  [top-up: existing 4.50h]"
    )


def test_format_styled_row_locked_uses_row_locked_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _color_on(monkeypatch)
    rendered = styling.format_styled_row(_locked_row(date(2026, 6, 3)))
    assert rendered[0][0] == "class:row.locked"


def test_format_styled_row_skipped_uses_row_skipped_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _color_on(monkeypatch)
    rendered = styling.format_styled_row(_skipped_row(date(2026, 6, 3)))
    assert rendered[0][0] == "class:row.skipped"


def test_format_styled_row_returns_plain_string_when_color_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _color_off_via_no_color(monkeypatch)
    rendered = styling.format_styled_row(_plain_row())
    assert isinstance(rendered, str)
    assert rendered == "Wed  2026-06-03  8.00h  [planned]"


# ---------- format_styled_header dispatch ----------


def test_format_styled_header_color_enabled_uses_row_header_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _color_on(monkeypatch)
    rendered = styling.format_styled_header()
    assert isinstance(rendered, list)
    assert rendered[0][0] == "class:row.header"
    assert "Day" in rendered[0][1]
    assert "State" in rendered[0][1]


def test_format_styled_header_returns_plain_string_when_color_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _color_off_via_no_color(monkeypatch)
    rendered = styling.format_styled_header()
    assert isinstance(rendered, str)
    assert "Day" in rendered and "State" in rendered


def test_select_kwargs_includes_style_when_color_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _color_on(monkeypatch)
    kwargs = styling.select_kwargs()
    assert "style" in kwargs and kwargs["style"] is not None


def test_select_kwargs_is_empty_when_color_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ``style=None`` leaks per `contracts/preview-rendering.md`."""
    _color_off_via_no_color(monkeypatch)
    assert styling.select_kwargs() == {}
