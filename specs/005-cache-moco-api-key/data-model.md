# Phase 1 Data Model: Cache the Moco API Key Locally

Two in-memory shapes and one on-disk shape. Nothing here changes the
Moco HTTP payloads.

## Entity: StoredCredential (on disk)

The persisted form of the API key. Exactly one per user; lives in the
per-user config file (see `contracts/credential-store.md`).

| Field | Type | Rules |
|-------|------|-------|
| `schema_version` | int | Currently `1`. A reader that sees any other value treats the store as absent (cache miss → re-prompt), exactly like `holidays.py` schema handling. |
| `token` | string | Non-empty, stripped. The Moco API key. A missing / empty / non-string value makes the whole store a miss. |

**Validation rules**:

- Read returns the token only when the file parses as a JSON object,
  `schema_version == 1`, and `token` is a non-empty string. Any other
  case → `None` (treated as "no stored key"), satisfying FR-009.
- Write persists `{"schema_version": 1, "token": "<key>"}` atomically and
  sets file mode `0o600` (FR-010, FR-011).
- The file carries **no** user-identifying metadata beyond the key
  itself.

**Lifecycle / state transitions**:

```
absent ──(prompt/env key authenticates)──▶ present
present ──(stored key rejected by Moco)──▶ absent  (deleted) ──▶ re-prompt
present ──(new key authenticates, differs)──▶ present (overwritten)
present ──(user deletes file manually)────▶ absent ──▶ re-prompt next run
```

## Entity: ApiCredentials (in memory) — modified

Existing dataclass in `models.py`. One change: the `source` literal gains
`"store"`.

| Field | Type | Change |
|-------|------|--------|
| `token` | string | unchanged; non-empty invariant in `__post_init__`. |
| `source` | `Literal["env", "store", "prompt"]` | **was** `Literal["env", "prompt"]`; add `"store"` for a key read from the on-disk store. |

`source` is used only for diagnostics and to drive persistence /
reject-recovery decisions — never to print the token. A `"store"`-sourced
key that authenticates needs no re-write; a `"store"`-sourced key that is
rejected triggers store deletion + re-prompt.

## Concept: Credential resolution order

Not a stored entity — the precedence applied by `auth.resolve_credentials`
(FR-005):

1. `MOCO_API_KEY` environment variable (→ `source="env"`)
2. StoredCredential file (→ `source="store"`)
3. Masked interactive prompt (→ `source="prompt"`)

After a successful authentication, a key whose value differs from the
stored token is written back, regardless of source (FR-005, FR-015).

## Relationship to existing model

`StoredCredential.token` ⇄ `ApiCredentials.token` are the same secret in
two representations (on-disk vs in-run). No other entity references the
credential; `MocoClient` continues to receive only the raw token string
(`moco_client.py`), never the dataclass or the file.
