# Feature Specification: Cache the Moco API Key Locally

**Feature Branch**: `005-cache-moco-api-key`

**Created**: 2026-06-22

**Status**: Draft

**Input**: User description: "when moco api key is put then save it locally also this should not be commited or be able to commited. Locally cache it do not ask the key multiple times"

## Clarifications

### Session 2026-06-22

- Q: How should the saved Moco API key be protected at rest? → A: Plaintext file in the per-user directory with owner-only permissions (stdlib-only, no new dependency); OS keychain / encryption is out of scope.
- Q: When should the key be written to the local store? → A: Only after it successfully authenticates against Moco, so a typo'd or invalid key is never cached.
- Q: Should a key supplied via the MOCO_API_KEY environment variable ever be written to the store? → A: Yes — once it authenticates, an env-var-supplied key is also persisted so later runs work without the env var.
- Q: Before saving a freshly entered key, should the tool ask for confirmation? → A: Save silently, without an extra confirmation prompt.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Enter the key once, never be asked again (Priority: P1)

A user runs the tool for the first time and is prompted for their Moco
API key. After they type it in and the run succeeds, the key is saved
to a private per-user location on their machine. On every later run the
tool finds the saved key and proceeds straight to its work without
prompting again.

**Why this priority**: This is the core of the request — eliminating the
repeated key prompt is the whole reason for the feature. Without it the
feature delivers nothing.

**Independent Test**: Start with no saved key, run the tool, supply a
valid key when prompted, let it complete. Run the tool a second time and
confirm it does **not** prompt for the key and operates with the same
credential.

**Acceptance Scenarios**:

1. **Given** no key has ever been saved, **When** the user runs the tool
   and enters a valid key at the prompt, **Then** the run proceeds and
   the key is persisted to the per-user store.
2. **Given** a valid key was saved on a previous run, **When** the user
   runs the tool again, **Then** the tool uses the saved key and does not
   prompt for it.
3. **Given** a valid key was saved on a previous run, **When** the user
   runs the tool repeatedly, **Then** the tool never re-prompts as long
   as the saved key keeps working.

---

### User Story 2 - The saved key can never be committed (Priority: P1)

The saved key lives outside the project's source tree, in a private
per-user location, so it can never be added to version control even by
accident. If any in-repository path were ever used to hold a key, the
repository is configured to ignore it so it cannot be staged or
committed.

**Why this priority**: The user explicitly required that the key "should
not be commited or be able to commited." A leaked credential is a
security incident, so this constraint is as important as the convenience
itself.

**Independent Test**: After a key is saved, inspect the project working
tree and `git status`; confirm the key file does not appear as a tracked,
staged, or untracked candidate for commit. Attempt to `git add` the
store location and confirm git refuses or the path is outside the repo
entirely.

**Acceptance Scenarios**:

1. **Given** a key has been saved, **When** the user inspects the project
   repository, **Then** the key file is not present anywhere inside the
   repository working tree.
2. **Given** a key has been saved, **When** the user runs the project's
   version-control status, **Then** no key material appears as a tracked,
   staged, or untracked file.
3. **Given** any in-repository fallback path for a key were to exist,
   **When** the user attempts to stage it, **Then** version control
   ignores the path and it cannot be committed.

---

### User Story 3 - A rejected saved key recovers gracefully (Priority: P2)

A previously saved key stops working (it was revoked, rotated, or
mistyped). On the next run the tool detects that the saved key is
rejected, discards it, prompts the user for a fresh key, and saves the
new working key in its place.

**Why this priority**: Caching a credential is only safe if a stale or
bad credential cannot lock the user out. This keeps the convenience from
becoming a trap, but the tool still works on first-time setup without it.

**Independent Test**: Save a key, then invalidate it (revoke at source or
corrupt the stored value). Run the tool and confirm it reports the
rejection, prompts for a new key, accepts a valid one, and reuses the new
key on the following run.

**Acceptance Scenarios**:

1. **Given** a saved key that the service now rejects, **When** the user
   runs the tool, **Then** the tool reports the rejection and prompts for
   a new key rather than failing silently or looping.
2. **Given** the user supplies a new valid key after a rejection, **When**
   the run completes, **Then** the new key replaces the old one in the
   store and is reused on later runs.
3. **Given** the stored key file is unreadable or malformed, **When** the
   user runs the tool, **Then** the tool ignores the bad store, prompts
   for a key, and rewrites a clean store.

---

### User Story 4 - Replace or remove the saved key (Priority: P3)

A user who changes machines, rotates their credential, or wants to stop
caching can replace or delete the saved key. Deleting the store returns
the tool to first-run behavior (it prompts again); supplying a key
through the existing environment-variable override takes precedence over
the saved one for that run.

**Why this priority**: Users need a clear, low-friction way to reset or
override a cached secret. It is important for trust but not required for
the primary save-and-reuse journey.

**Independent Test**: With a key saved, delete the store file and confirm
the next run prompts again. Separately, with a key saved, set the
environment-variable override to a different key and confirm that run
uses the override.

**Acceptance Scenarios**:

1. **Given** a saved key, **When** the user deletes the store file with
   ordinary file tools, **Then** the next run prompts for a key as if it
   were the first run.
2. **Given** a saved key, **When** the environment-variable override is
   set for a run, **Then** that run uses the override instead of the saved
   key, and once the override authenticates it replaces the saved key.
3. **Given** the user wants to change the saved key, **When** they trigger
   a re-prompt (via a rejected key or by clearing the store), **Then** the
   newly entered key becomes the saved key.

---

### Edge Cases

- **No write permission to the store location**: the run still completes
  using the key the user entered, but a warning notes the key could not
  be saved and they may be prompted again next time.
- **Concurrent runs**: two invocations writing the store at the same time
  must not corrupt it — the store is updated atomically.
- **Environment-variable override present**: the override is used for that
  run and takes precedence; once it authenticates, it is also written to
  the saved store (FR-015).
- **Empty or whitespace-only key entered**: treated as no key — the tool
  re-prompts or errors rather than saving a blank credential.
- **Store file present but contains no usable key**: treated as no saved
  key; the tool prompts and rewrites the store.
- **Multiple users on one machine**: each user's key lives under their own
  per-user location and is not shared.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST persist a Moco API key to a private per-user
  location on the local machine — but only after that key successfully
  authenticates against Moco — so a known-good key can be reused on later
  runs and a typo'd or invalid key is never cached.
- **FR-002**: The system MUST reuse a previously saved key automatically
  and MUST NOT prompt for the key when a usable saved key is available.
- **FR-003**: The saved key MUST be stored outside the project's source
  repository so it can never be added to version control.
- **FR-004**: The system MUST ensure that no key material can be staged or
  committed to the repository, including configuring the repository to
  ignore any in-repository path that could ever hold a key.
- **FR-005**: The system MUST resolve the key in a defined precedence
  order: the existing environment-variable override first, then the saved
  store, then an interactive prompt. A key obtained from any of these
  sources MUST, once it authenticates successfully, be written to the
  saved store (including a key supplied via the environment variable) so
  later runs work without re-supplying it.
- **FR-006**: When a saved key is rejected by the Moco service, the system
  MUST discard it, inform the user, and prompt for a new key.
- **FR-007**: When the user enters a new key after a rejected or missing
  one, the system MUST save the new key once it authenticates
  successfully, replacing any previous stored value.
- **FR-008**: The system MUST treat an empty or whitespace-only entry as
  "no key" and MUST NOT persist a blank credential.
- **FR-009**: The system MUST handle an unreadable, malformed, or empty
  store gracefully by ignoring it, prompting for a key, and rewriting a
  clean store.
- **FR-010**: The system MUST restrict access to the saved key so it is
  readable only by the owning user account, to the extent the host
  operating system supports file permissions.
- **FR-011**: The system MUST update the store atomically so concurrent
  runs cannot corrupt it.
- **FR-012**: The system MUST allow the user to remove or replace the
  saved key using ordinary operating-system file tools, with deletion
  returning the tool to first-run prompt behavior.
- **FR-013**: When the key cannot be written to the store, the system MUST
  still complete the current run using the entered key and MUST warn the
  user that the key was not saved.
- **FR-014**: The system MUST NOT print, log, or otherwise display the key
  value during normal operation; the key prompt MUST remain masked.
- **FR-015**: When the environment-variable override supplies a key that
  authenticates successfully, the system MUST persist it to the saved
  store, replacing any previous stored value, so subsequent runs no longer
  require the environment variable.
- **FR-016**: The system MUST persist a validated key silently, without an
  additional save-confirmation prompt.

### Key Entities *(include if feature involves data)*

- **Saved Credential**: The persisted Moco API key plus the minimum
  metadata needed to use and validate it (e.g., the key value and a
  schema/version marker). Holds exactly one key per user. Lives in a
  private per-user location, never in the repository.
- **Credential Source**: The resolved origin of the key for a given run —
  environment-variable override, saved store, or interactive prompt —
  used to decide precedence and whether to persist.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After entering a valid key once, a user completes 100% of
  subsequent runs without being prompted for the key again, for as long
  as the key remains valid.
- **SC-002**: Reusing a saved key adds no noticeable startup delay
  compared with supplying the key by environment variable (within 100ms).
- **SC-003**: No key material ever appears as a tracked, staged, or
  untracked commit candidate in the repository in any tested scenario.
- **SC-004**: When a saved key is rejected, the user reaches a working
  state by entering a new key in a single run, with no infinite loop or
  silent failure.
- **SC-005**: Deleting the saved key file returns the tool to first-run
  prompt behavior on the very next run, 100% of the time.
- **SC-006**: The saved key is never visible in terminal output, logs, or
  the repository across all tested flows.

## Assumptions

- The store lives in the standard per-user configuration or cache
  location for the host operating system (the same per-user-directory
  approach already used for the locally cached holiday data), which by
  construction is outside the project repository.
- The key is stored in a simple local file protected by owner-only file
  permissions, consistent with the project's existing constraint of using
  the standard library and adding no new third-party dependency. A full
  OS keychain / encrypted-vault integration is out of scope for this
  feature.
- The existing `MOCO_API_KEY` environment-variable override continues to
  work and takes precedence over the saved store, preserving current
  scripted and CI usage. Per the 2026-06-22 clarification, an env-var key
  that authenticates is also written to the saved store (it is no longer a
  run-only value).
- "Usable saved key" means a non-empty key read from a well-formed store;
  the service-side validity check is the existing authentication step,
  which already detects rejected keys.
- Only one Moco key per user is cached; multiple accounts or profiles are
  out of scope.
- Storing the key as a local file (rather than an encrypted vault) is an
  accepted trade-off for this tool, mitigated by owner-only permissions
  and keeping the file outside the repository.
