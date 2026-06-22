# Contract: On-Disk Credential Store (v1)

The local file that holds the cached Moco API key. Owned by
`src/moco_filler/credential_store.py`. Consumed by `auth.py`.

## Location

Per-user **config** directory (outside any repository → FR-003):

| OS | Path |
|----|------|
| macOS | `~/Library/Application Support/moco-filler/credentials.json` |
| Linux | `${XDG_CONFIG_HOME:-$HOME/.config}/moco-filler/credentials.json` |
| Windows | `%APPDATA%\moco-filler\credentials.json` (fallback `~/AppData/Roaming/...` when `APPDATA` unset) |

Directory name `moco-filler`, file name `credentials.json`. The directory
is created lazily on first write with mode `0o700`.

## File schema (version 1)

```json
{
  "schema_version": 1,
  "token": "<the Moco API key>"
}
```

- `schema_version` (int): currently `1`. Any other value → store treated
  as absent.
- `token` (string): non-empty, stripped. The API key.
- No additional fields are written. No user identity, timestamps, or
  request data are stored (the key alone is sufficient; minimises what a
  leaked file exposes).

File permissions: `0o600` (owner read/write only), enforced on POSIX
after the atomic write; best-effort on Windows.

## Module API

```python
def read_stored_token() -> Optional[str]:
    """Return the stored token, or None on any miss.

    None when: file missing, unreadable, not JSON, not an object,
    schema_version != 1, or token missing/empty/non-string. Never raises
    (FR-009).
    """

def write_token(token: str) -> None:
    """Persist token atomically; set 0o600. Raises OSError on FS failure.

    Serialise to a sibling temp file, fsync, os.replace, chmod 0o600.
    Caller (auth.persist_if_new) catches OSError → warn + continue
    (FR-013). Creates the parent dir (0o700) if needed.
    """

def delete_token() -> None:
    """Remove the store file. No-op if already absent. Never raises for
    a missing file (used on reject-recovery, FR-006)."""

def _store_path() -> Path:
    """Per-OS config path resolver. Stdlib-only (no platformdirs)."""
```

## Behavioural guarantees

| ID | Guarantee |
|----|-----------|
| CS-1 | A malformed, empty, or wrong-version file reads as `None` and never crashes the CLI (FR-009). |
| CS-2 | `write_token` is atomic: a concurrent reader sees either the old file or the new file, never a partial one (FR-011). |
| CS-3 | The written file is mode `0o600` on POSIX (FR-010). |
| CS-4 | `delete_token` returns the tool to first-run state (next `read_stored_token` → `None`) (FR-012, SC-005). |
| CS-5 | The token value is never logged or printed by this module (FR-014). |

## Test surface (unit, no real home dir)

`_store_path` is redirected to `tmp_path` per test. Cases: missing file,
malformed JSON, empty object, wrong `schema_version`, empty/blank token,
round-trip write→read, mode is `0o600` after write, atomic overwrite
preserves a valid prior value on success, delete then read → `None`,
write into a non-existent directory creates it.
