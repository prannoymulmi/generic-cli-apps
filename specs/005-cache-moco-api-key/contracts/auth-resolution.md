# Contract: Credential Resolution & Persistence

Owned by `src/moco_filler/auth.py`. Wires the on-disk store
(`credential_store.py`) into the run, decides precedence, persists after
a successful authentication, and recovers from a rejected stored key.

## Public API

```python
def resolve_credentials() -> ApiCredentials:
    """Resolve the key for this run in precedence order (FR-005):
    1. MOCO_API_KEY env var  → source="env"
    2. stored file           → source="store"
    3. masked prompt         → source="prompt"
    Raises CredentialMissingError if the prompt yields an empty key
    (FR-008)."""

def prompt_for_credentials() -> ApiCredentials:
    """Force the masked questionary.password prompt (source="prompt").
    Used by the reject-recovery path. Empty entry → CredentialMissingError."""

def persist_if_new(creds: ApiCredentials) -> None:
    """Write the token to the store iff it differs from the stored value.
    Swallows OSError with a single stderr warning (FR-013). Persists keys
    from ANY source once validated, including env (FR-005, FR-015)."""

def forget_stored_credential() -> None:
    """Delete the store (reject-recovery). Never raises (FR-006)."""

def authenticate(validate: Callable[[str], T]) -> tuple[ApiCredentials, T]:
    """Resolve → validate → (on reject) re-prompt → persist. Returns the
    working credentials and whatever `validate` returned."""
```

`validate(token)` is injected by the caller. It MUST raise
`AuthError` when Moco rejects the key and return any value otherwise. This
keeps `auth.py` free of HTTP imports and makes the loop unit-testable.

## Resolution precedence (FR-005)

```
MOCO_API_KEY set & non-empty? ── yes ─▶ ApiCredentials(token, "env")
        │ no
        ▼
stored token present?          ── yes ─▶ ApiCredentials(token, "store")
        │ no
        ▼
masked prompt                  ─────────▶ ApiCredentials(token, "prompt")
                                          (empty → CredentialMissingError)
```

## authenticate() state machine

```
creds ← resolve_credentials()
try:
    result ← validate(creds.token)          # raises AuthError on 401/403
except AuthError:
    if creds.source == "store":
        forget_stored_credential()
        stderr: "Saved Moco API key was rejected; please re-enter."
    creds ← prompt_for_credentials()        # force a fresh key
    result ← validate(creds.token)          # 2nd failure → AuthError (exit 2)
persist_if_new(creds)                        # silent on success (FR-016)
return (creds, result)
```

## Behavioural guarantees

| ID | Guarantee | Spec |
|----|-----------|------|
| AR-1 | A valid stored key authenticates with **no prompt**. | FR-002, SC-001 |
| AR-2 | A key is persisted **only after** it authenticates. | FR-001, FR-007 |
| AR-3 | A key from any source (env/store/prompt) is persisted once validated, when it differs from the stored value. | FR-005, FR-015 |
| AR-4 | A rejected **stored** key is deleted, the user is warned, and re-prompted within the same run. | FR-006 |
| AR-5 | A rejected freshly-entered key fails the run (`AuthError`, exit 2) — no infinite loop. | SC-004 |
| AR-6 | A malformed/empty store is ignored and falls through to the prompt; the prompt's valid key rewrites a clean store. | FR-009 |
| AR-7 | `MOCO_API_KEY` still takes precedence for the run. | FR-005 |
| AR-8 | A save failure (OSError) warns on stderr and the run continues. | FR-013 |
| AR-9 | Persistence is silent — no confirmation prompt. | FR-016 |
| AR-10 | The token is never printed/logged; the prompt stays masked. | FR-014 |

## cli.py wiring (illustrative)

Replaces today's `resolve_credentials()` → `MocoClient` → `get_session()`
sequence (`cli.py:90-94`):

```python
def _connect(token: str) -> tuple[MocoClient, int]:
    client = MocoClient(token=token, base_url=MOCO_BASE_URL)
    return client, client.get_session()      # raises AuthError on 401/403

_creds, (client, user_id) = authenticate(_connect)
```

The `MocoClient` is constructed exactly once; `get_session()` is called
exactly once on the happy path. No change to the stdout-scrape contract or
exit codes from feature 001.

## Test surface (unit, faked validate + faked store)

env→store→prompt precedence; stored key validates with no prompt
(AR-1); persist-after-validate writes the store (AR-2); env key persisted
(AR-3); stored key rejected → store deleted + re-prompt → success (AR-4);
re-entered key also rejected → AuthError propagates (AR-5); malformed
store → prompt path (AR-6); save OSError → warning + run continues
(AR-8); persisted value equals stored → no redundant write.
