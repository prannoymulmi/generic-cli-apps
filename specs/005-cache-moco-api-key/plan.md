# Implementation Plan: Cache the Moco API Key Locally

**Branch**: `005-cache-moco-api-key` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-cache-moco-api-key/spec.md`

## Summary

Today the Moco API key is resolved fresh every run — from `MOCO_API_KEY`
or a masked prompt — and is **never** written to disk (`auth.py`). This
feature adds a private per-user credential store so the user supplies the
key at most once, while guaranteeing the key can never be committed.

The approach mirrors the on-disk pattern already proven by feature 004's
`holidays.py` (stdlib-only per-OS directory resolver, atomic
temp-file + `os.replace` write, graceful handling of a malformed store),
but stores the credential in the per-user **config** directory rather
than the cache directory — a credential must survive a cache wipe and is
configuration, not a regenerable cache.

Per the 2026-06-22 clarification session, the key is persisted **only
after it successfully authenticates** (the existing `client.get_session()`
call is the validation point), a key from any source — including
`MOCO_API_KEY` — is persisted once it authenticates, the save happens
**silently**, and the store is a **plaintext file with owner-only
permissions** (no OS keychain, no new dependency).

Work decomposes into: one new module (`credential_store.py`), thin
extensions to `auth.py` (resolution precedence + a validate-persist-retry
orchestrator) and `models.py` (one new `source` value), one wiring change
in `cli.py`, and a defensive `.gitignore` entry. No new top-level
dependency is introduced.

## Technical Context

**Language/Version**: Python 3.9+ (Constitution §I; `requires-python =
">=3.9"` in `pyproject.toml`).

**Primary Dependencies**:

- Standard library only for the store (`json`, `os`, `pathlib`,
  `tempfile`, `sys`, `stat`) — no `platformdirs`, consistent with
  `holidays.py` (FR — no new dependency).
- `questionary` (already shipped) — the existing masked
  `questionary.password` prompt is reused unchanged for the re-prompt
  path.
- No HTTP dependency added to `auth.py`: validation is injected as a
  callback so `auth.py` stays transport-agnostic and unit-testable.

**Storage**:

- One JSON file at the standard per-user **config** location for the host
  OS:
  - macOS: `~/Library/Application Support/moco-filler/credentials.json`
  - Linux: `${XDG_CONFIG_HOME:-$HOME/.config}/moco-filler/credentials.json`
  - Windows: `%APPDATA%\moco-filler\credentials.json`
    (falls back to `~/AppData/Roaming` when `APPDATA` is unset)
- File created with mode `0o600`, parent directory `0o700`, to the
  extent the OS enforces POSIX permissions (FR-010).
- Holds exactly one key (`{"schema_version": 1, "token": "..."}`).

**Testing**: `pytest`. New `tests/test_credential_store.py` (path
resolver per-OS, atomic write, permission bits, read of missing /
malformed / empty store, delete). Extended `tests/test_auth.py` (env →
store → prompt precedence, persist-after-validate, reject-then-reprompt,
env-key persistence, save-failure warning). Extended
`tests/test_models.py` (new `source` literal). The store path is
redirected to a `tmp_path` per test; no real home directory is touched.

**Target Platform**: macOS / Linux / Windows terminal — same as features
001/004. The config-directory branch is the only OS-specific concern and
stays stdlib-only.

**Performance Goals**: human-interactive. The store-hit path is a single
small JSON read (< 10 ms), well inside the SC-002 100 ms budget — it
replaces a blocking prompt, so it is strictly faster than the status quo.

**Constraints**:

- No new top-level dependency (mirrors `holidays.py`).
- The key MUST live outside the repository so it can never be committed
  (FR-003); the per-user config dir satisfies this by construction, with
  a defensive `.gitignore` entry as belt-and-suspenders (FR-004).
- Atomic store updates so concurrent invocations cannot corrupt the file
  (FR-011) — same temp-file + `os.replace` technique as `holidays.py`.
- The key is never printed or logged; the prompt stays masked (FR-014);
  `ApiCredentials.source` lets diagnostics name the origin without ever
  showing the token (existing pattern).
- The stdout-scrape contract from feature 001 is untouched; any new
  status/warning text goes to **stderr** only.

**Scale/Scope**: exactly one key per user; the file is well under 1 KB.
The only non-trivial control flow is the resolve → validate → (on reject)
re-prompt → persist orchestration in `auth.py`.

## Constitution Check

*Initial gate — re-checked after Phase 1 design; both gates pass.*

| Principle | How this plan satisfies it |
|-----------|----------------------------|
| **I. Python3 & Questionary-First** | No new TUI library. The re-prompt reuses the existing `questionary.password` masked prompt. `credential_store.py` is non-interactive. |
| **II. Atomic Commits** | Decomposes into small, independently green commits: store module + tests; `models.py` source field + test; `auth.py` resolution/orchestrator + tests; `cli.py` wiring; `.gitignore` guard. Each leaves `pytest` green and is reviewable in ≤ 5 min. |
| **III. Clean Code & Readability** | `credential_store.py` exposes a small named API: `read_stored_token()`, `write_token()`, `delete_token()`, `_store_path()`. `auth.py` gains `authenticate(validate)`, `persist_if_new()`, `forget_stored_credential()`, `prompt_for_credentials()` — each single-purpose and type-hinted. |
| **IV. Unit Tests Only** | Path resolver, atomic write, permission bits, malformed-store handling, precedence, persist-after-validate, reject-recovery are all pure-Python and unit-testable. Validation is an injected callback faked per test; no network and no real home dir are touched. |
| **V. Single Responsibility & Modularity** | `credential_store.py` owns the on-disk store only; `auth.py` owns resolution + orchestration; `cli.py` gains one call and a thin `validate` closure; `models.py` gains one literal value. Nothing imports `requests` outside `moco_client.py`/`holidays.py`; `auth.py` stays transport-agnostic via the callback. |

**Gate result**: PASS. No violations; the `Complexity Tracking` section
is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/005-cache-moco-api-key/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 — store location, persist timing, reject recovery, permissions, no-commit guarantee
├── data-model.md        # Phase 1 — StoredCredential + extended ApiCredentials + source enum
├── quickstart.md        # Phase 1 — where the key lives per OS, how to clear/override it
├── contracts/
│   ├── credential-store.md   # On-disk store file schema (v1) + path + permissions
│   └── auth-resolution.md    # Resolution precedence + persist-after-auth + reject-recovery state machine
├── checklists/
│   └── requirements.md  # Already PASS-ing
├── spec.md              # Feature spec (clarifications integrated)
└── tasks.md             # Phase 2 output — written by /speckit-tasks, NOT here
```

### Source Code (repository root)

One new module, three lightly-modified existing modules, one new test
file plus two updated test files, and a `.gitignore` guard.

```text
src/
└── moco_filler/
    ├── __init__.py
    ├── __main__.py
    ├── cli.py                 # (modified) wire authenticate(validate) in place of resolve→get_session
    ├── auth.py                # (modified) env→store→prompt precedence + authenticate() orchestrator + persist/forget helpers
    ├── credential_store.py    # (NEW) per-user config-dir resolver + atomic read/write/delete + 0o600 perms
    ├── moco_client.py
    ├── calendar_utils.py
    ├── planner.py
    ├── preview.py
    ├── styling.py
    ├── holidays.py
    ├── models.py              # (modified) ApiCredentials.source gains "store"
    └── errors.py              # (unchanged) reuse AuthError + CredentialMissingError

tests/
├── test_auth.py              # (modified) +precedence, +persist-after-validate, +reject-recovery, +env-persist, +save-failure
├── test_credential_store.py  # (NEW) path resolver, atomic write, perms, missing/malformed/empty, delete
├── test_models.py            # (modified) +case for the new "store" source value
├── test_calendar_utils.py
├── test_moco_client.py
├── test_planner.py
├── test_preview_logic.py
├── test_styling.py
└── test_holidays.py

.gitignore                    # (modified) defensive ignore for any in-repo credential file (FR-004)
```

**Structure Decision**: Reuse the single-project layout from features
001/002/004. Rationale:

- The new logic fits one module (`credential_store.py`), so a sub-package
  would over-structure it — same call made for `holidays.py`.
- The store touches one file at one path; no `store/` subpackage is
  justified.
- The new test file (`test_credential_store.py`) follows the existing
  one-test-per-module convention.
- `auth.py` keeps resolution + orchestration because that is exactly its
  current responsibility ("resolve the credential for this run"); the
  on-disk concern is split out to honour §V.

## Complexity Tracking

> No constitution violations to justify; this section is intentionally empty.
