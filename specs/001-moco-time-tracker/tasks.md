# Tasks: Moco Monthly Time Tracker CLI

**Input**: Design documents from `/specs/001-moco-time-tracker/`
**Branch**: `001-moco-time-tracker`
**Date**: 2026-06-01

**Tests**: Unit tests are MANDATORY per Constitution §IV (Unit Tests Only — non-negotiable). Each story's implementation tasks are paired with the unit-test tasks that cover their business logic. The live Questionary preview loop is intentionally not unit-tested (per `research.md` §8); the pure helpers extracted from it are.

**Organization**: Tasks are grouped by user story so each story can be implemented, committed, and tested as an independent atomic increment per Constitution §II.

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel — different files, no incomplete dependencies.
- **[Story]**: Required for user-story phases (US1, US2, US3); omitted in Setup, Foundational, and Polish phases.

## Path Conventions

Single-project layout from `plan.md` → "Project Structure":

- Source: `src/moco_filler/`
- Tests: `tests/`
- Packaging: `pyproject.toml`, `requirements.txt` at repo root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton and packaging so every subsequent task has a place to land and a way to install / run.

- [X] T001 Create the package skeleton — `src/moco_filler/__init__.py`, `src/moco_filler/__main__.py`, and the `tests/` directory at repo root — matching the layout in `plan.md` → Project Structure.
- [X] T002 Create `pyproject.toml` at repo root with `[project]` metadata (name `moco-filler`, Python `>=3.9` per Constitution Technology Stack, dev-pinned to 3.11 per `plan.md`), runtime deps `questionary` + `requests`, dev deps `pytest` + `responses`, and a `[project.scripts]` entry `moco-filler = "moco_filler.cli:main"` per `contracts/cli.md` § Invocation.
- [X] T003 [P] Create `requirements.txt` at repo root mirroring `pyproject.toml`'s runtime and dev deps with pinned versions for reproducibility (Constitution Dependency Management).
- [X] T004 [P] Create `README.md` at repo root that points contributors at `specs/001-moco-time-tracker/quickstart.md` for install + run instructions (per `plan.md` → Project Structure).
- [X] T005 [P] Add `.gitignore` at repo root covering `__pycache__/`, `.venv/`, `*.egg-info/`, `.pytest_cache/`, `dist/`, `build/` to keep build artifacts out of commits (supports Constitution §II atomic commits).

**Checkpoint**: `pip install -e .` succeeds and `moco-filler --help` runs (even if it does nothing useful yet).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared data shapes, error/exit-code vocabulary, and date math — everything every user story depends on.

**⚠️ CRITICAL**: No user-story tasks can begin until Phase 2 is complete.

- [X] T006 Create `src/moco_filler/errors.py` defining domain exceptions (`CredentialMissingError`, `AuthError`, `NoProjectsError`, `NoTasksError`, `NothingToSubmitError`, `BulkTotalFailureError`, `BulkPartialFailureError`) and a single mapping from each exception class to the exit codes 1–7 in `research.md` §6 + `contracts/cli.md` § Exit codes.
- [X] T007 Create `src/moco_filler/models.py` defining the dataclasses from `data-model.md` — `ApiCredentials`, `Project`, `Task`, `PlannedEntry` (including the new `existing_hours_total` field, `hours` range `[0, 8]`, default = `max(Decimal(0), Decimal(8) − existing_hours_total)`, `already_logged` triggered at `existing_hours_total ≥ 8`), `SubmissionBatch`, `EntryResult`, and `SubmissionResult` with its derived properties (`created_count`, `failed_count`, `succeeded`, `any_created`).
- [X] T008 [P] Write unit tests for `models.py` in `tests/test_models.py` covering: weekend-date rejection on `PlannedEntry`, `hours` out-of-range rejection (negative, `> 8`), `already_logged` invariant (must coexist with `included=False`, immutable after construction), `is_submitable` truth table across the `included × hours × already_logged` matrix, and `SubmissionResult` derived properties across all-created / all-failed / mixed inputs.
- [X] T009 [P] Create `src/moco_filler/calendar_utils.py` with `parse_month(value: str | None) -> tuple[int, int]` (strict `YYYY-MM`, defaulting to the current calendar month at process start per `FR-002`) and `weekday_dates(year: int, month: int) -> list[date]` enumerating Mon–Fri only using `datetime` + `calendar` (no third-party date libs per `research.md` §4).
- [X] T010 [P] Write unit tests for `calendar_utils.py` in `tests/test_calendar_utils.py` covering: 28/30/31-day months, leap-year February, months that start or end on a weekend, invalid `--month` strings (`"2026-13"`, `"2026/06"`, `"abc"`), and the default-to-current-month branch.

**Checkpoint**: `pytest tests/test_models.py tests/test_calendar_utils.py` is green. The foundation is ready and user-story work can begin.

---

## Phase 3: User Story 1 — Fill a full month + approve before submitting (Priority: P1) 🎯 MVP

**Goal**: End-to-end happy path. With a Moco API key supplied via `MOCO_API_KEY`, the user runs `moco-filler --month 2026-06`, sees a preview, approves it, and Moco accepts the bulk submission. (Credential safety hardening lives in US2.)

**Independent Test** (spec § US1): Export a valid sandbox key, run the CLI for a chosen month, navigate the preview, approve, and verify in the Moco web UI that an 8-hour Administration entry exists for every weekday and none on the weekends.

### Tests for User Story 1 (Constitution §IV — mandatory) ⚠️

> Per Constitution §IV, write each test alongside or before its implementation. Don't merge untested code.

- [X] T011 [P] [US1] Write unit tests for `moco_client.py` in `tests/test_moco_client.py` using `responses` to stub `GET /session`, `GET /projects/assigned`, `GET /activities`, and `POST /activities/bulk`. Cover: request shape (URL, `Authorization: Token token=…` header, 15s timeout, query params — verifying NO `project_id`/`task_id` on `/activities` per `contracts/moco-http.md`), happy 2xx → expected dataclass, 401/403 → `AuthError`, opaque non-2xx on `/bulk` → every `EntryResult` `"failed"` with the shared upstream reason, and a per-row response on `/bulk` → mixed `EntryResult` list (FR-011).
- [X] T012 [P] [US1] Write unit tests for `planner.py` in `tests/test_planner.py` covering: empty-month case (every weekday at the default 8h), fully-filled days (existing total ≥ 8h → `already_logged=True`, `included=False`), partial-day top-up (existing 4.5h → planned 3.5h), and the multi-project sum (existing entries spread across two projects on the same date still count toward the daily total — Q4 clarification).

### Implementation for User Story 1

- [X] T013 [US1] Create `src/moco_filler/moco_client.py` with a `MocoClient` class whose constructor takes the API token + base URL and pre-configures a `requests.Session` with the `Authorization: Token token=…` header and a default 15s timeout per `contracts/moco-http.md` § Base. Implement `get_session() -> int` returning the authenticated user's id.
- [X] T014 [US1] In `src/moco_filler/moco_client.py`, implement `get_projects_assigned() -> list[Project]` that parses the response (with embedded `tasks`) into `Project`/`Task` dataclasses from `models.py` and raises `NoProjectsError` on an empty list.
- [X] T015 [US1] In `src/moco_filler/moco_client.py`, implement `get_activities(from_date: date, to_date: date, user_id: int) -> list[dict]` — `from_date`/`to_date`/`user_id` only; explicitly do NOT pass `project_id` or `task_id` per the 2026-06-01 clarification in `contracts/moco-http.md` § `GET /activities`.
- [X] T016 [US1] In `src/moco_filler/moco_client.py`, implement `bulk_create(batch: SubmissionBatch) -> SubmissionResult` that serializes the request body per `contracts/moco-http.md` (`seconds = int(hours * 3600)`, fixed `"Administration"` description, `billable=false`), calls `POST /activities/bulk`, and builds the `SubmissionResult` by either parsing a per-row response into individual `EntryResult`s or — when the response is opaque — applying the overall 2xx/non-2xx outcome to every row (FR-011, `data-model.md` § `SubmissionResult` construction rule).
- [X] T017 [P] [US1] Create `src/moco_filler/planner.py` with `build_planned_entries(year: int, month: int, existing_activities: list[dict]) -> list[PlannedEntry]` that (a) enumerates weekdays via `calendar_utils`, (b) sums `existing_activities` `hours` per `date` to populate `existing_hours_total` (across all projects/tasks per the Q4 clarification), (c) flips `already_logged=True` when the sum is `≥ 8h`, and (d) sets `hours = max(0, 8 − existing_hours_total)` otherwise (FR-005, FR-012).
- [X] T018 [P] [US1] Create `src/moco_filler/preview.py` with the read-only preview — a `questionary.select` rendering one row per `PlannedEntry` in the four states from `contracts/cli.md` (`[planned]`, `[top-up: existing Xh]`, `[already logged]`, `[skipped]`), plus the `✅ Approve & submit` / `❌ Cancel` choices. Per-row editing belongs to US3; this task implements navigation + approve/cancel only.
- [X] T019 [US1] Create `src/moco_filler/cli.py` with `main()` that wires the happy path: `argparse` for `--month` (per `contracts/cli.md`), read `MOCO_API_KEY` from `os.environ` (raise `CredentialMissingError` if unset — the masked-prompt fallback is added by US2/T024), build a `MocoClient`, call `get_session()` → `get_projects_assigned()` → project picker (`questionary.select`) → task picker (defaulting to `"Administration"` per FR-004) → `get_activities()` → `planner.build_planned_entries()` → `preview` → on `Approve` build a `SubmissionBatch` and call `bulk_create()` → render the three stdout lines + exit codes 0/6/7 from `contracts/cli.md` based on `SubmissionResult`. On `Cancel`, print `Nothing was submitted.` and exit `0`. Catch domain exceptions from `errors.py` at the top level and map to their declared exit codes.
- [X] T020 [US1] In `src/moco_filler/__main__.py`, call `cli.main()` so `python -m moco_filler` and the `moco-filler` console script entry from T002 share the same entrypoint.
- [ ] T021 [US1] Run the quickstart happy path against a sandbox Moco account (`quickstart.md` §3) — pick an Administration task, approve, confirm the success line, and verify in the Moco web UI that an 8-hour entry exists for every Mon–Fri of the chosen month and zero on the weekend (FR-014, SC-002).


**Checkpoint**: US1 ships as the MVP. The CLI fills a month end-to-end given an exported `MOCO_API_KEY`. The interactive masked-prompt path is added in US2 next.

---

## Phase 4: User Story 2 — Safe credential handling (Priority: P1)

**Goal**: Per FR-001, the API key comes from `MOCO_API_KEY` or a masked prompt, is held only in memory for one run, and never lands on disk, in logs, or in argv. Per FR-013, auth failures exit cleanly with a plain-language message.

**Independent Test** (spec § US2): Run the CLI in a freshly-cloned directory, supply the key interactively, complete a run (success, cancel, AND a forced crash), then verify via `grep` that no file inside the repository contains the key and that the masked prompt did not echo it (SC-004).

### Tests for User Story 2 (Constitution §IV — mandatory) ⚠️

- [X] T022 [P] [US2] Write unit tests for `auth.py` in `tests/test_auth.py` covering: env var present and non-empty → prompt is NOT invoked; env var unset → `questionary.password` is invoked (use a monkeypatched fake); empty / whitespace-only token (env or prompt) → `CredentialMissingError`; `ApiCredentials.source` is `"env"` vs `"prompt"` correctly; the resolved token is NOT written to stderr/stdout via captured-output fixtures.

### Implementation for User Story 2

- [X] T023 [US2] Create `src/moco_filler/auth.py` with `resolve_credentials() -> ApiCredentials` that returns `ApiCredentials(token=..., source="env")` when `MOCO_API_KEY` is set and non-empty (after `.strip()`), else uses `questionary.password("Moco API key:")` and returns `ApiCredentials(token=..., source="prompt")`. The function MUST NOT write the token anywhere, MUST NOT log it, and MUST NOT accept it via `argv`.
- [X] T024 [US2] In `src/moco_filler/cli.py`, replace the env-var-only credential read from T019 with `auth.resolve_credentials()`. The resolved `ApiCredentials.token` is passed only to the `MocoClient` constructor and to no other code path. Update any error-rendering path to mask the token (e.g., never f-string it into a message).
- [ ] T025 [US2] In `src/moco_filler/moco_client.py`, harden the 401/403 path on `get_session()` so it raises `AuthError` with a token-free message (`"Authentication failed: check your Moco API key."` only). In `cli.py`, catch `AuthError` at the top level and exit with code `2` per `contracts/cli.md`, ensuring nothing token-shaped is printed to stderr (verified via the test in T022).
- [ ] T026 [US2] Execute the SC-004 verification per `quickstart.md` §5 — run the CLI three times (successful run, user-cancelled run, deliberately crashed run via Ctrl-C mid-prompt), then run `grep -r "<first 8 chars of your test key>" .` from the repo root. Expected output: empty. If grep finds anything, fix the leak before declaring US2 complete.

**Checkpoint**: Credentials are safe across success, cancel, and crash exit paths. Combined with US1, the CLI is independently usable by a real user.

---

## Phase 5: User Story 3 — Edit the preview before approving (Priority: P2)

**Goal**: Per FR-008 and Q2/Q3 clarifications, the user can skip a row or change a row's hours within `[0, 8]`. Setting hours to 0 auto-skips. The running monthly total updates as edits happen. Already-logged rows remain locked.

**Independent Test** (spec § US3): Open the preview, navigate to a row, change its hours and/or mark it as skipped, then approve and confirm the submitted batch reflects the edits exactly.

### Tests for User Story 3 (Constitution §IV — mandatory) ⚠️

- [ ] T027 [P] [US3] Extend `tests/test_planner.py` with helper-function tests for `toggle_skipped(row)` and `set_hours(row, value)` covering: edit hours to a valid in-range value, edit hours to `0` → `included=False` (Q2 auto-skip), edit hours to a negative value → `ValueError`, edit hours above `8` → `ValueError` (Q3 cap), skip toggle on plain and skipped rows, skip refused on `already_logged=True` rows (FR-012).
- [ ] T028 [P] [US3] Write unit tests for the preview's pure helpers in `tests/test_preview_logic.py` per `research.md` §8 — covering the row-format string builder (one case per state: plain / top-up / already-logged / skipped) and the `next_included_row` / running-total computation. Explicitly do NOT exercise the live `questionary.select` loop.

### Implementation for User Story 3

- [ ] T029 [US3] In `src/moco_filler/planner.py`, add `toggle_skipped(row: PlannedEntry) -> PlannedEntry` and `set_hours(row: PlannedEntry, value: Decimal) -> PlannedEntry` as pure functions (no UI imports) so they can be unit-tested per `research.md` §8. Enforce the `[0, 8]` validation on `set_hours` and the auto-skip on `0`.
- [ ] T030 [US3] Extend `src/moco_filler/preview.py` with the per-row sub-menu — variants for plain / top-up / skipped / already-logged rows per `contracts/cli.md` § Interactive flow step 6. Dispatch `Skip this row` / `Include this row` / `Change hours` / `Back`; the `Change hours` action uses `questionary.text` with input validation backed by `set_hours` from T029. Re-render the preview after every accepted edit.
- [ ] T031 [US3] Run the US3 independent test against the sandbox account — change one row to `4`, skip another, approve, then verify in Moco that the 4h row was created at 4h and the skipped row produced no entry.

**Checkpoint**: All three user stories are independently functional. The CLI is feature-complete for v1.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T032 [P] Add a `[tool.pytest.ini_options]` block (or `pytest.ini`) configuring `testpaths = ["tests"]` and `addopts = "-ra -q"` so `pytest` runs the full suite cleanly from the repo root.
- [ ] T033 [P] Update `README.md` to embed the install + run snippet from `quickstart.md` §§1–3 so a clone-and-run contributor gets the one-page reference without digging.
- [ ] T034 Run the full test suite (`pytest`) plus the SC-002 weekend smoke check from `quickstart.md` §5 (`grep` the Moco activities view for weekend dates → expect empty) as a final gate before declaring the feature complete.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies; start immediately.
- **Foundational (Phase 2)**: depends on Setup. BLOCKS all user-story work.
- **US1 (Phase 3)**: depends on Foundational. MVP — should ship first.
- **US2 (Phase 4)**: depends on Foundational AND on the `cli.py` + `moco_client.py` scaffolding from US1 (T019, T025 modify them).
- **US3 (Phase 5)**: depends on Foundational AND on `preview.py` + `planner.py` from US1.
- **Polish (Phase 6)**: depends on US1 (for `pyproject.toml`) and benefits from all user stories being merged.

### Within-story dependencies

- **US1**: T013 → T014/T015/T016 (all in `moco_client.py`, sequential by file). T017 (planner) is file-independent from `moco_client.py` and can land in parallel with T014–T016. T018 (preview) is file-independent and can run alongside T017. T019 (cli glue) depends on T013–T018. T020 depends on T019. T021 (manual sandbox run) is last in the phase.
- **US2**: T023 (auth) is independent of US1 file edits and can be written in parallel with T024–T025 if a dummy `cli.py`/`moco_client.py` is available. In practice land T023, then T024 (cli.py change), then T025 (moco_client.py hardening), then T026 (SC-004 verification).
- **US3**: T029 (planner helpers) → T030 (preview wiring uses them). T027 and T028 (tests) can be written first per TDD or alongside.

### Parallel opportunities

- All `[P]` tasks within Setup (T003/T004/T005) can run together.
- T008 and T010 (test files) can run in parallel with each other and with their respective implementation tasks under TDD.
- In US1: T011 (tests for moco_client) and T012 (tests for planner) can be written in parallel; T017 (planner.py) and T018 (preview.py) can be written in parallel with T013–T016 because they touch different files.
- In US3: T027 and T028 (different test files) run in parallel.

---

## Parallel Example: kicking off User Story 1

```bash
# Write the test scaffolds in parallel first (TDD per Constitution §IV):
Task: "Write unit tests for moco_client.py in tests/test_moco_client.py"
Task: "Write unit tests for planner.py in tests/test_planner.py"

# Then implement the two file-independent modules in parallel:
Task: "Create src/moco_filler/planner.py with build_planned_entries()"
Task: "Create src/moco_filler/preview.py read-only preview"
```

---

## Implementation Strategy

### MVP first (US1 only)

1. Finish Phase 1: Setup.
2. Finish Phase 2: Foundational (BLOCKS everything).
3. Finish Phase 3: US1.
4. **Stop and validate** against US1's Independent Test (T021).
5. Tag / demo. The CLI is usable end-to-end with `MOCO_API_KEY` exported.

### Incremental delivery

1. Ship US1 (above).
2. Add US2 → re-run US2's Independent Test (T026). Now safe for general use — masked prompt + SC-004 verification.
3. Add US3 → re-run US3's Independent Test (T031). v1 feature-complete.
4. Polish (Phase 6) gates the final tag.

### Solo developer rhythm

Stories run sequentially (US1 → US2 → US3), each producing a chain of small commits (one per task) that satisfy Constitution §II. Don't open US2 before US1's checkpoint passes.

---

## Notes

- **Commit message rule**: per Constitution §II + the 1.1.0 amendment, every commit MUST explain *why* in the subject line (when it fits) or in a body paragraph. "Refactor", "cleanup", or "update" alone is rejected. Bake the "why" into each task's commit before moving on.
- **Tests are not optional** — Constitution §IV makes unit tests non-negotiable for business logic. The "no integration tests for MVP" carve-out applies only to HTTP and the live Questionary loop; everything else gets tested.
- **No alternative TUI / prompt library** — Constitution §I requires Questionary for every interactive prompt. Don't reach for `rich`, `prompt_toolkit`, or `curses`, even if a feature looks easier there.
- **The API key is sacred** — see SC-004. Any task that touches `cli.py`, `auth.py`, `moco_client.py`, or `errors.py` must double-check it neither writes the token to a file nor includes it in any rendered string.
- **Avoid cross-story file churn** — when US2/US3 edit a file from US1, keep the diff scoped to the clarified concern; don't refactor unrelated code in the same commit.
