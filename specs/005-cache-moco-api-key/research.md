# Phase 0 Research: Cache the Moco API Key Locally

All Technical Context items resolved; no NEEDS CLARIFICATION remain.
Several decisions were already fixed by the 2026-06-22 clarification
session in `spec.md` and are recorded here for traceability.

## §1. Where the credential lives

**Decision**: One JSON file in the per-user **config** directory:

- macOS: `~/Library/Application Support/moco-filler/credentials.json`
- Linux: `${XDG_CONFIG_HOME:-$HOME/.config}/moco-filler/credentials.json`
- Windows: `%APPDATA%\moco-filler\credentials.json`

**Rationale**:

- A per-user OS directory is **outside the repository by construction**,
  which is what makes FR-003 ("can never be committed") true without
  relying on discipline.
- **Config**, not cache: `holidays.py` uses the cache directory
  (`~/Library/Caches`, `XDG_CACHE_HOME`) because a holiday list is
  regenerable. A credential is *not* regenerable from nothing and must
  survive a "clear caches" sweep, so it belongs in the config /
  Application Support / Roaming AppData location instead.
- Stdlib-only resolver mirrors `holidays._cache_path()` — no
  `platformdirs` dependency (no-new-dependency constraint).

**Alternatives considered**:

- *OS keychain (Keychain / Credential Manager / Secret Service)* —
  rejected by clarification Q1: needs a third-party dependency and
  per-platform code, violating the stdlib-only constraint for marginal
  benefit on a single-user developer tool.
- *Cache directory (reuse `holidays._cache_path`)* — rejected: caches are
  routinely cleared, which would silently delete the saved key and defeat
  the "don't ask twice" goal.
- *Project-local dotfile (e.g. `.moco-filler` in repo)* — rejected: it
  lives inside the repo and could be committed; the whole point of FR-003
  is to keep the key out of the tree.

## §2. Protection at rest

**Decision**: Plaintext JSON, file mode `0o600`, parent dir mode `0o700`,
set explicitly after creation (and via `mkstemp` defaults during the
atomic write).

**Rationale**: Clarification Q1 fixed plaintext-with-permissions. On
POSIX, `0o600` makes the file unreadable by other accounts. On Windows
`chmod` is largely a no-op; FR-010 is scoped "to the extent the OS
supports," and `%APPDATA%` is already per-user. No encryption: a
locally-derived key would sit beside the ciphertext and add complexity
for no real attacker-model gain (clarification Q1).

**Alternatives considered**: encrypted-at-rest file — rejected by Q1.

## §3. When the key is persisted

**Decision**: Persist **only after** the key authenticates successfully.
The existing first authenticated call — `client.get_session()` in
`cli.py` — is the validation point. Persist only when the validated token
**differs** from what is already stored (avoids redundant writes and the
no-op case where the key came from the store unchanged).

**Rationale**: Clarification Q2 — never cache a typo'd/invalid key, so the
stored key is always known-good. Mapping to existing code: `get_session()`
raises `AuthError` (exit code 2) on HTTP 401/403, giving a clean
success/failure signal with no new error type.

**Alternatives considered**: persist immediately on entry — rejected by
Q2 (would cache bad keys and trigger avoidable reject-recovery next run).

## §4. Resolution precedence and env-var persistence

**Decision**: Resolve in order **`MOCO_API_KEY` env → stored file →
masked prompt** (FR-005). A key from *any* source — including the env var
— is written to the store once it authenticates (FR-005, FR-015,
clarification Q3).

**Rationale**: Preserves existing scripted/CI behaviour (env still wins
for a run) while letting a first env-var run "seed" the store so later
interactive runs need nothing. Q3 explicitly reversed the spec's original
"env applies to that run only" stance.

**Alternatives considered**: env-var key never persisted — rejected by Q3.

## §5. Recovery when a stored key is rejected

**Decision**: A small orchestrator in `auth.py`,
`authenticate(validate)`:

1. `creds = resolve_credentials()` (env → store → prompt).
2. `try: result = validate(creds.token)`.
3. On `AuthError`: if `creds.source == "store"`, delete the store and
   warn on stderr ("Saved Moco API key was rejected; please re-enter.");
   then `creds = prompt_for_credentials()` and `validate` again. A second
   failure propagates as `AuthError` (exit 2) — no infinite loop (SC-004).
4. On success: `persist_if_new(creds)`; return `(creds, result)`.

`validate` is an injected callback so `auth.py` never imports the HTTP
client and the loop is unit-testable with a fake validator. In `cli.py`
the callback constructs the `MocoClient` once and calls `get_session()`,
returning `(client, user_id)` so there is no second round-trip.

**Rationale**: FR-006/FR-007/FR-009 + SC-004. Keeping the loop in
`auth.py` keeps `cli.py` thin (§V) and makes the state machine the unit
under test. A malformed/empty store is treated as a cache miss by the
store reader (returns `None`), so it naturally falls through to the prompt
(FR-009) without special-casing in the orchestrator.

**Alternatives considered**:

- Orchestration inline in `cli.py` — rejected: harder to unit-test and
  thickens the glue layer (§V).
- `auth.py` importing `MocoClient` directly — rejected: couples auth to
  the transport; the callback keeps it transport-agnostic.

## §6. Atomic, corruption-safe writes

**Decision**: Reuse the `holidays._save_cache` technique: serialise to a
sibling temp file via `tempfile.mkstemp` in the target directory,
`flush` + `os.fsync`, then `os.replace` (atomic on POSIX and Windows),
unlinking the temp file on failure. Apply `chmod 0o600` to the final
file.

**Rationale**: FR-011 — concurrent CLI runs cannot observe a half-written
file. Proven in `holidays.py`; same disk-failure handling (raise → caller
treats as save-failure).

## §7. Graceful save failure

**Decision**: If the write raises `OSError` (read-only FS, permission
denied, full disk), the run **continues** with the in-memory validated
token and a single stderr warning ("Could not save the Moco API key; you
may be prompted again next time."). The exception never propagates.

**Rationale**: FR-013 — caching is a convenience, not a precondition for
the current run. Mirrors the `holidays.get_hamburg_holidays` save-failure
swallow.

## §8. The "cannot be committed" guarantee

**Decision**: Two layers. (a) Primary: the file lives in the per-user
config dir, outside the working tree, so `git` never sees it. (b)
Defensive: add an ignore entry to the repo `.gitignore` for any
in-repository credential filename (e.g. `credentials.json`,
`.moco-filler/`), so even an accidental in-tree copy cannot be staged
(FR-004).

**Rationale**: FR-003 is satisfied structurally; FR-004 wants the repo
itself to refuse the path. Both are cheap and independent.

**Alternatives considered**: a pre-commit hook scanning for key material —
rejected as out of scope and heavier than the stated requirement; the
out-of-tree location already makes accidental commit impossible.

## §9. Model and error surface

**Decision**: Extend `ApiCredentials.source` from `Literal["env",
"prompt"]` to `Literal["env", "store", "prompt"]`. No new exception
class: reuse `AuthError` (exit 2) for a rejected key and
`CredentialMissingError` (exit 2) for an empty entry, both already in
`errors.py`.

**Rationale**: `source` already exists precisely to name the origin for
diagnostics without printing the token; "store" is the third natural
value. Reusing existing exit codes keeps the `cli.md` exit-code contract
unchanged.
