---

description: "Task list for feature 005 — cache the Moco API key locally"
---

# Tasks: Cache the Moco API Key Locally

**Input**: Design documents from `/specs/005-cache-moco-api-key/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED. Constitution §IV mandates unit tests for all
business logic, co-located in `tests/`. The HTTP boundary is never
contacted — validation is an injected fake; the store path is redirected
to `tmp_path` so no real home directory is touched.

**Organization**: Tasks are grouped by user story (spec.md priorities) so
each story is an independently testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 / US4 — maps to spec.md user stories
- All paths are repository-relative (single-project layout from features 001/004)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm baseline before touching code

- [ ] T001 Run `pytest` and confirm the suite is green; confirm no new dependency is needed (`requests`, `questionary` already pinned in `pyproject.toml`) per plan.md "no new top-level dependency"

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The on-disk store and the model change that every key-handling story depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T002 Create the store module with the per-OS config-dir resolver `_store_path()` (macOS `~/Library/Application Support`, Linux `${XDG_CONFIG_HOME:-$HOME/.config}`, Windows `%APPDATA%`; dir `moco-filler`, file `credentials.json`) in `src/moco_filler/credential_store.py` per contracts/credential-store.md
- [ ] T003 Implement `read_stored_token()` (None on missing/malformed/empty/wrong-version, never raises), `write_token()` (atomic tempfile + `os.replace`, `chmod 0o600`, dir `0o700`, raises `OSError` on FS failure), and `delete_token()` (no-op if absent, never raises) in `src/moco_filler/credential_store.py`
- [ ] T004 [P] Unit tests for the store in `tests/test_credential_store.py` (redirect `_store_path` to `tmp_path`): missing file, malformed JSON, empty object, wrong `schema_version`, blank token → None; write→read round-trip; mode is `0o600` after write; atomic overwrite preserves a valid prior value; delete then read → None; write creates the parent dir
- [ ] T005 [P] Extend `ApiCredentials.source` to `Literal["env", "store", "prompt"]` in `src/moco_filler/models.py`
- [ ] T006 [P] Unit test asserting an `ApiCredentials` with `source="store"` is valid (and the non-empty-token invariant still holds) in `tests/test_models.py`

**Checkpoint**: Store I/O and the model are ready — user stories can begin

---

## Phase 3: User Story 1 - Enter the key once, never be asked again (Priority: P1) 🎯 MVP

**Goal**: A validated key is saved silently and reused on later runs with no prompt.

**Independent Test**: Start with no store; run with a valid key at the prompt → run succeeds and the store file appears. Run again → no prompt, same credential used.

### Implementation for User Story 1

- [ ] T007 [US1] Implement `resolve_credentials()` precedence **env → store → prompt** (env via `MOCO_API_KEY`→`source="env"`; `credential_store.read_stored_token()`→`source="store"`; masked `questionary.password`→`source="prompt"`; empty prompt → `CredentialMissingError`) in `src/moco_filler/auth.py`
- [ ] T008 [US1] Implement `prompt_for_credentials()` (force masked prompt, `source="prompt"`) and `persist_if_new(creds)` (write via `credential_store.write_token` only when token differs from the stored value; persists ANY source; swallow `OSError` with one stderr warning per FR-013) in `src/moco_filler/auth.py`
- [ ] T009 [US1] Implement `authenticate(validate)` happy path — `resolve_credentials()` → `result = validate(token)` → `persist_if_new(creds)` → return `(creds, result)`; persist is silent (FR-016) — in `src/moco_filler/auth.py`
- [ ] T010 [US1] Wire `cli.py`: replace the `resolve_credentials()` → `MocoClient(...)` → `get_session()` block (`cli.py:90-94`) with a `_connect(token)` closure returning `(client, user_id)` and `_creds, (client, user_id) = authenticate(_connect)` in `src/moco_filler/cli.py`
- [ ] T011 [P] [US1] Unit tests in `tests/test_auth.py` (fake `validate`, fake store, monkeypatched `questionary.password`): env/store/prompt precedence; a valid stored key authenticates with **no prompt** (AR-1); a validated prompt/env key is written to the store (AR-2); no redundant write when the resolved key already equals the stored value

**Checkpoint**: First-run-prompts-then-reuses works end to end (MVP core)

---

## Phase 4: User Story 2 - The saved key can never be committed (Priority: P1) 🎯 MVP

**Goal**: The key lives outside the repo by construction, and the repo refuses any in-tree key file.

**Independent Test**: After a key is saved, `git status` shows nothing key-related; the resolved store path is outside the working tree; `git add credentials.json` is ignored.

### Implementation for User Story 2

- [ ] T012 [P] [US2] Add defensive ignore entries for any in-repository key file (`credentials.json`, `.moco-filler/`) to `.gitignore` per FR-004
- [ ] T013 [P] [US2] Unit test in `tests/test_credential_store.py` asserting `_store_path()` resolves under the per-user config dir for each `sys.platform` (darwin/linux/win32, monkeypatched) and is **not** inside the repository working tree (FR-003)

**Checkpoint**: The no-commit guarantee is verified structurally and defensively

---

## Phase 5: User Story 3 - A rejected saved key recovers gracefully (Priority: P2)

**Goal**: A stored key that Moco rejects is discarded, the user is warned, re-prompted, and the new key saved — no lock-out, no loop.

**Independent Test**: Save a key, then make `validate` reject it; run → tool warns, prompts, accepts a new key, and the next run reuses the new key. A second consecutive rejection exits with `AuthError` (code 2).

### Implementation for User Story 3

- [ ] T014 [US3] Add `forget_stored_credential()` (delete the store via `credential_store.delete_token`, never raises) in `src/moco_filler/auth.py`
- [ ] T015 [US3] Extend `authenticate(validate)` with reject-recovery: on `AuthError`, if `creds.source == "store"` call `forget_stored_credential()` and warn on stderr ("Saved Moco API key was rejected; please re-enter."), then `prompt_for_credentials()` and `validate` once more; a second `AuthError` propagates (exit 2, no loop) in `src/moco_filler/auth.py`
- [ ] T016 [P] [US3] Unit tests in `tests/test_auth.py`: stored key rejected → store deleted + re-prompt → success persisted (AR-4); re-entered key also rejected → `AuthError` propagates with no infinite loop (AR-5, SC-004); malformed/empty store falls through to the prompt and rewrites a clean store (AR-6)

**Checkpoint**: Stale/revoked keys self-heal within one run

---

## Phase 6: User Story 4 - Replace or remove the saved key (Priority: P3)

**Goal**: Manual deletion returns to first-run behavior; `MOCO_API_KEY` overrides the stored key for a run and, once validated, replaces it.

**Independent Test**: With a key saved, delete the file → next run prompts. Separately, set `MOCO_API_KEY` to a different key → that run uses the override and the store is updated to it.

### Implementation for User Story 4

- [ ] T017 [P] [US4] Unit tests in `tests/test_auth.py` exercising the existing resolution/persistence behavior for the replace/remove flows: `MOCO_API_KEY` takes precedence over the stored key for the run (AR-7); a validated env key is persisted, replacing the prior stored value (AR-3 / FR-015); deleting the store (`delete_token`) makes the next `resolve_credentials()` fall through to the prompt (SC-005); a `write_token` `OSError` yields a stderr warning and the run still completes (AR-8)

**Checkpoint**: Users can reset or override the cached key predictably

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and end-to-end validation

- [ ] T018 [P] Document the local key cache in `src/moco_filler/README.md` (per-OS location, `MOCO_API_KEY` override now also persists, how to clear the file), aligned with quickstart.md
- [ ] T019 Run the full `pytest` suite and confirm green; spot-check that no token value appears in any stderr/stdout/log line across the flows (FR-014, SC-006)
- [ ] T020 Validate quickstart.md end to end: first run prompts and saves; second run no prompt; `rm` the store → prompts again

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none
- **Foundational (Phase 2)**: depends on Setup — **BLOCKS all user stories** (store module + model)
- **US1 (Phase 3)**: depends on Foundational
- **US2 (Phase 4)**: depends on Foundational (uses `_store_path`); independent of US1
- **US3 (Phase 5)**: depends on US1 — extends `authenticate()`
- **US4 (Phase 6)**: depends on US1 (precedence/persist) + Foundational (`delete_token`); mostly verification
- **Polish (Phase 7)**: depends on the user stories being delivered

### User Story Dependencies

- US1 and US2 are both P1 and mutually independent → the MVP.
- US3 and US4 build on the `authenticate()` / resolution code introduced in US1 (same file `auth.py`), so they follow US1 rather than running fully parallel to it.

### Within Each Story

- Foundational store API (T002–T003) before any `auth.py` work.
- `resolve_credentials` (T007) before `authenticate` (T009) before cli wiring (T010).
- `forget_stored_credential` (T014) before the reject-recovery branch (T015).
- Tests are authored alongside and must pass before the story is considered done.

### Parallel Opportunities

- T004, T005, T006 (different files) run in parallel within Foundational.
- T012, T013 (US2) run in parallel and alongside US1 once Foundational is done.
- T016 (US3) and T017 (US4) edit the same `tests/test_auth.py` as T011 — sequence edits to that file to avoid conflicts.

---

## Parallel Example: Foundational

```bash
# After T002–T003 land the store module, run these together:
Task: "Unit tests for the store in tests/test_credential_store.py"   # T004
Task: "Extend ApiCredentials.source in src/moco_filler/models.py"    # T005
Task: "Unit test for the new 'store' source in tests/test_models.py" # T006
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 — both P1)

1. Phase 1: Setup
2. Phase 2: Foundational (store module + model) — CRITICAL, blocks everything
3. Phase 3: US1 — enter once, reused thereafter
4. Phase 4: US2 — verify it can never be committed
5. **STOP and VALIDATE**: a saved key is reused with no prompt and never appears in `git status`

### Incremental Delivery

1. Setup + Foundational → store ready
2. US1 → first-run-then-reuse (demo the prompt disappearing on run 2)
3. US2 → confirm out-of-tree + `.gitignore` guard
4. US3 → rotate/revoke a key and watch it self-heal
5. US4 → delete-to-reset and env-var override/persist
6. Polish → docs + quickstart validation

---

## Notes

- [P] = different files, no dependency on an incomplete task.
- The token is never printed or logged; `ApiCredentials.source` names the
  origin for diagnostics without exposing the secret.
- Commit after each task or logical group, with a message that explains
  *why* (Constitution §II).
- `tests/test_auth.py` is touched by T011, T016, T017 — keep those edits
  sequential even though they belong to different stories.
