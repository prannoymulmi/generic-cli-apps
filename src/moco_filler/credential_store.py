"""On-disk store for the cached Moco API key.

Owns the read/write/delete lifecycle for the single per-user credential
file feature 005 introduces. Implements
``specs/005-cache-moco-api-key/contracts/credential-store.md``:

- One JSON file in the per-user *config* directory — deliberately the
  config dir, not the cache dir ``holidays.py`` uses, because a
  credential must survive a "clear caches" sweep (research.md §1).
- Stdlib-only per-OS path resolver — no ``platformdirs`` dependency.
- Atomic ``os.replace`` writes so concurrent CLI runs cannot observe a
  half-written file (FR-011).
- Owner-only file permissions (``0o600``) on POSIX (FR-010).
- A missing / malformed / wrong-version / empty store reads as ``None``
  and never raises (FR-009).

The key value is never logged or printed by this module (FR-014).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional


STORE_SCHEMA_VERSION = 1
_STORE_DIR_NAME = "moco-filler"
_STORE_FILE_NAME = "credentials.json"

_FILE_MODE = 0o600
_DIR_MODE = 0o700


# ---- config-path resolver (research.md §1) ------------------------------


def _store_path() -> Path:
    """Return the per-user *config* file path for the host OS.

    Stdlib-only — no ``platformdirs`` dependency. The credential lives in
    the config directory (not the cache directory) so it is not wiped by
    cache-clearing tools. The directory is created lazily on first write.
    """
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "").strip()
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    elif sys.platform.startswith("linux"):
        xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
        base = Path(xdg) if xdg else Path.home() / ".config"
    else:
        base = Path.home() / ".config"
    return base / _STORE_DIR_NAME / _STORE_FILE_NAME


# ---- read (contracts/credential-store.md) -------------------------------


def read_stored_token() -> Optional[str]:
    """Return the stored API key, or ``None`` on any miss.

    ``None`` means: file missing, unreadable, not JSON, not an object,
    ``schema_version`` mismatch, or a missing / empty / non-string
    ``token``. Never raises — a corrupt store must never crash the CLI
    (FR-009).
    """
    path = _store_path()
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
    if data.get("schema_version") != STORE_SCHEMA_VERSION:
        return None
    token = data.get("token")
    if not isinstance(token, str):
        return None
    token = token.strip()
    return token or None


# ---- write --------------------------------------------------------------


def write_token(token: str) -> None:
    """Persist ``token`` atomically with owner-only permissions.

    Serialise to a sibling temp file, ``fsync``, ``os.replace`` into
    place, then ``chmod 0o600``. The parent directory is created with
    ``0o700`` if missing. Raises ``OSError`` on filesystem failure
    (read-only FS, permission denied, disk full); the caller
    (``auth.persist_if_new``) treats that as a non-fatal save failure
    (FR-013).
    """
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, _DIR_MODE)
    except OSError:
        # Best-effort on platforms where chmod is a no-op (e.g. Windows).
        pass

    payload: Dict[str, Any] = {
        "schema_version": STORE_SCHEMA_VERSION,
        "token": token,
    }
    fd, tmp_path = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_path, _FILE_MODE)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---- delete -------------------------------------------------------------


def delete_token() -> None:
    """Remove the store file. No-op if it is already absent.

    Used by the reject-recovery path (FR-006) and to support manual
    reset (FR-012). Never raises for a missing file.
    """
    try:
        _store_path().unlink()
    except FileNotFoundError:
        pass
    except OSError:
        # An undeletable file is not fatal; the next run will overwrite
        # it once a fresh key authenticates.
        pass
