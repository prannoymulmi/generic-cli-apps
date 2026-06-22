"""Unit tests for moco_filler.credential_store.

The store path is redirected to a per-test ``tmp_path`` so no real home
directory is ever touched. Covers the contract in
``specs/005-cache-moco-api-key/contracts/credential-store.md``.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from moco_filler import credential_store


@pytest.fixture
def store_file(tmp_path, monkeypatch):
    """Point ``_store_path`` at a temp file and return that path."""
    path = tmp_path / "moco-filler" / "credentials.json"

    def _fake_path():
        return path

    monkeypatch.setattr(credential_store, "_store_path", _fake_path)
    return path


# ---- read: miss cases ---------------------------------------------------


def test_read_returns_none_when_file_missing(store_file):
    assert credential_store.read_stored_token() is None


def test_read_returns_none_on_malformed_json(store_file):
    store_file.parent.mkdir(parents=True)
    store_file.write_text("{not json", encoding="utf-8")
    assert credential_store.read_stored_token() is None


def test_read_returns_none_on_empty_object(store_file):
    store_file.parent.mkdir(parents=True)
    store_file.write_text("{}", encoding="utf-8")
    assert credential_store.read_stored_token() is None


def test_read_returns_none_on_wrong_schema_version(store_file):
    store_file.parent.mkdir(parents=True)
    store_file.write_text(
        json.dumps({"schema_version": 999, "token": "abc"}),
        encoding="utf-8",
    )
    assert credential_store.read_stored_token() is None


def test_read_returns_none_on_non_object_json(store_file):
    store_file.parent.mkdir(parents=True)
    store_file.write_text(json.dumps(["abc"]), encoding="utf-8")
    assert credential_store.read_stored_token() is None


@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_read_returns_none_on_blank_or_missing_token(store_file, blank):
    store_file.parent.mkdir(parents=True)
    store_file.write_text(
        json.dumps({"schema_version": 1, "token": blank}),
        encoding="utf-8",
    )
    assert credential_store.read_stored_token() is None


def test_read_returns_none_on_non_string_token(store_file):
    store_file.parent.mkdir(parents=True)
    store_file.write_text(
        json.dumps({"schema_version": 1, "token": 1234}),
        encoding="utf-8",
    )
    assert credential_store.read_stored_token() is None


# ---- write / round-trip -------------------------------------------------


def test_write_then_read_round_trip(store_file):
    credential_store.write_token("secret-key-123")
    assert credential_store.read_stored_token() == "secret-key-123"


def test_write_creates_parent_directory(store_file):
    assert not store_file.parent.exists()
    credential_store.write_token("abc")
    assert store_file.exists()


def test_read_strips_surrounding_whitespace(store_file):
    store_file.parent.mkdir(parents=True)
    store_file.write_text(
        json.dumps({"schema_version": 1, "token": "  padded  "}),
        encoding="utf-8",
    )
    assert credential_store.read_stored_token() == "padded"


@pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX permission bits not enforced on Windows"
)
def test_write_sets_owner_only_file_mode(store_file):
    credential_store.write_token("abc")
    mode = stat.S_IMODE(os.stat(store_file).st_mode)
    assert mode == 0o600


def test_atomic_overwrite_preserves_value_on_success(store_file):
    credential_store.write_token("first")
    credential_store.write_token("second")
    assert credential_store.read_stored_token() == "second"
    # No leftover temp files beside the store.
    siblings = list(store_file.parent.iterdir())
    assert siblings == [store_file]


# ---- delete -------------------------------------------------------------


def test_delete_removes_file_and_read_returns_none(store_file):
    credential_store.write_token("abc")
    assert store_file.exists()
    credential_store.delete_token()
    assert not store_file.exists()
    assert credential_store.read_stored_token() is None


def test_delete_is_noop_when_file_absent(store_file):
    # Must not raise.
    credential_store.delete_token()
    assert credential_store.read_stored_token() is None


# ---- path resolver ------------------------------------------------------


def test_store_path_resolves_under_config_dir_per_platform(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert "Application Support" in str(credential_store._store_path())

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xdg-config")
    assert str(credential_store._store_path()).startswith("/tmp/xdg-config")

    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert ".config" in str(credential_store._store_path())


def test_store_path_is_outside_the_repository(monkeypatch):
    """FR-003: the key file can never live inside the repo working tree."""
    repo_root = Path(__file__).resolve().parents[1]
    for platform in ("darwin", "linux", "win32"):
        monkeypatch.setattr(sys, "platform", platform)
        resolved = credential_store._store_path().resolve()
        assert repo_root not in resolved.parents
        assert resolved.is_relative_to(Path.home())
