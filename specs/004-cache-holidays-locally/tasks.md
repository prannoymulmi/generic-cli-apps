# Tasks: Cache Hamburg Holidays Locally After One Download (bundled with 003)

**Input**: Design documents from `/specs/004-cache-holidays-locally/`

**Branch**: `004-cache-holidays-locally`

**Date**: 2026-06-04

**Bundling note**: This task list implements **both** feature 003
(`003-hamburg-holidays-skip`, the user-visible side) and feature 004
(`004-cache-holidays-locally`, the source-and-caching side) as a
single coherent deliverable, per `plan.md` § Summary. The two specs
are tightly coupled — feature 004 amends feature 003's
"bundled-catalogue" assumption — and shipping them together avoids a
throwaway implementation of the bundled path.

**Tests**: Unit tests are MANDATORY per Constitution §IV (Unit Tests
Only — non-negotiable). Each story's implementation tasks are paired
with the unit-test tasks that cover their pure helpers. The live
`date.nager.at` endpoint is intentionally never contacted from the
test suite — a fake `requests.Session` is injected.

**Organization**: Tasks are grouped by user story so each story can
be implemented, committed, and tested as an independent atomic
increment per Constitution §II.

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel — different files, no incomplete dependencies.
- **[Story]**: Required for user-story phases (US1, US2, US3); omitted in Setup, Foundational, and Polish phases.

## Path Conventions

Single-project layout from `plan.md` → "Project Structure":

- Source: `src/moco_filler/`
- Tests: `tests/`

No new top-level dependencies — `requests` is already in via
`moco_client.py` (FR-010 of spec.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Nothing new — the package skeleton, `pyproject.toml`,
`.gitignore`, `requirements.txt`, and pytest configuration are
already present from feature 001, and this feature adds no new
top-level dependency (`requests` is already pinned).

*This phase is intentionally empty for feature 004.*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Stand up the `holidays.py` module (cache + fetch +
validator + public accessor) and extend `PlannedEntry` with
`holiday_name`. Both US1 (planner consumes the catalogue) and US2
(preview renders the name) depend on these two pieces being in
place.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

### Tests for Foundational (Constitution §IV — mandatory) ⚠️

> Per Constitution §IV, write each test alongside or before its implementation. Don't merge untested code.

- [X] T001 [P] Extend `tests/test_models.py` with a test asserting `PlannedEntry`'s new optional field: `holiday_name` defaults to `None`, setting it to a string does not trip any existing `__post_init__` invariant, and a holiday row with `holiday_name="Karfreitag"` + `already_logged=True` + `included=False` is constructible (the FR-005 precedence shape).
- [X] T002 [P] Create `tests/test_holidays.py` with tests for `_cache_path()` returning the expected per-OS path under monkeypatched `sys.platform` and env vars: macOS → `~/Library/Caches/moco-filler/holidays.json`, Linux with `XDG_CACHE_HOME` set → `$XDG_CACHE_HOME/moco-filler/holidays.json`, Linux without it → `~/.cache/moco-filler/holidays.json`, Windows → `%LOCALAPPDATA%/moco-filler/Cache/holidays.json`.
- [X] T003 [P] In `tests/test_holidays.py`, add tests for `_load_cache(path, region, year)`: happy path returns a `list[Holiday]`; missing file, malformed JSON, missing `schema_version`, schema_version ≠ 1, missing region, missing year, and malformed entries all return `None`. None of these paths raise.
- [X] T004 [P] In `tests/test_holidays.py`, add tests for `_save_cache(path, region, year, entries)`: writes a JSON file that `_load_cache` can read back unchanged; preserves OTHER years inside the same file (FR-012); creates the parent directory on first write; on a read-only parent directory, raises an exception (caught by the call site, not by the writer itself).
- [X] T005 [P] In `tests/test_holidays.py`, add tests for `_validate_response(payload, year)`: accepts a list of Nager-shaped dicts; rejects non-list (`ValueError`); rejects entries with missing `date` or off-year `date` (`ValueError`); accepts both `localName` and the `name` fallback; filters Hamburg-applicable entries (federal `counties=null` kept, `counties=["DE-HH"]` kept, `counties=["DE-BY"]` dropped); imposes no count envelope (zero or 200 entries both pass).
- [X] T006 [P] In `tests/test_holidays.py`, add tests for `_fetch_with_retry(year, session)`: succeeds on first attempt → returns immediately; succeeds on third attempt → returns; all three attempts fail → raises `HolidayFetchError`; total wall-clock is bounded at ~5 s (use a monkeypatched `time.monotonic` + `time.sleep` to assert the budget check fires). Use an injected fake `Session` whose `.get()` returns canned `Response`-shaped objects (do not mock `requests` globally).
- [X] T007 [P] In `tests/test_holidays.py`, add tests for `get_hamburg_holidays(year)`: cache hit → returns the cached dict, never instantiates a Session; cache miss → calls the fetch path AND writes the cache AND prints the FR-015 status line to stderr (`capsys.readouterr().err`); fetch failure after retries → returns `{}` (FR-007 fallback) AND does NOT write the cache AND does NOT propagate the exception.

### Implementation for Foundational

- [X] T008 In `src/moco_filler/models.py`, extend `PlannedEntry` with one new optional field `holiday_name: Optional[str] = None`. No changes to `__post_init__` invariants. Bare `dataclasses.replace` calls in `planner.py` keep working because `replace` copies all unmentioned fields.
- [X] T009 Create `src/moco_filler/holidays.py` with the module docstring + the `_cache_path()` per-OS resolver from `research.md` §2. Import only `os`, `sys`, `pathlib`. ~15 lines of code; one branch per platform.
- [X] T010 In `src/moco_filler/holidays.py`, add the `Holiday` frozen dataclass (`data-model.md` § `Holiday`) and `_load_cache(path, region, year) -> Optional[list[Holiday]]` per `contracts/holiday-cache.md` § Read semantics. Every internal exception is caught and translated to `None`; the function MUST NOT raise.
- [X] T011 In `src/moco_filler/holidays.py`, add `_save_cache(path, region, year, entries) -> None` per `contracts/holiday-cache.md` § Write semantics — read-merge-write with atomic `os.replace`. Reading the existing cache uses `_load_cache`; if it can't be read, start from a fresh `{"schema_version": 1, "regions": {}}` skeleton.
- [X] T012 In `src/moco_filler/holidays.py`, add `_validate_response(payload, year) -> list[Holiday]` per `research.md` §6 and `contracts/holiday-source.md` § Response shape: structural check + year check + Hamburg-applicability filter. Raises `ValueError` on any failure. Imports `datetime.date` and `typing`.
- [X] T013 In `src/moco_filler/holidays.py`, add `HolidayFetchError(Exception)` (module-private — NOT added to `errors.py`) and `_fetch_with_retry(year, session=None) -> list[Holiday]` per `research.md` §5 — 3-attempt loop with backoffs `[0.0, 0.2, 0.6]` and per-attempt timeout `1.5 s`; total wall-clock budget `5.0 s` enforced via `time.monotonic()` before each attempt. Catches `requests.RequestException` and `ValueError` (the latter covers `_validate_response`'s rejections per FR-016 / FR-017). Builds a lazy `requests.Session` on first call when `session is None`.
- [X] T014 In `src/moco_filler/holidays.py`, add the public `get_hamburg_holidays(year: int) -> dict[date, str]` orchestrator: try `_load_cache`; on miss, print the FR-015 stderr status line, call `_fetch_with_retry`, call `_save_cache`, return the catalogue as a dict; on fetch failure, catch `HolidayFetchError` and return `{}` (FR-007 fallback). Save-failures (e.g., read-only filesystem) are caught and logged-as-non-fatal — the run continues with the in-memory catalogue.

**Checkpoint**: The `holidays` module is complete and unit-tested. The `PlannedEntry` model carries the new field with the right default. Neither US1's planner extension nor US2's preview render exists yet, so the CLI is functionally identical to feature 002 at this point — but the foundation is laid.

---

## Phase 3: User Story 1 — Hamburg holidays are auto-skipped from the plan (Priority: P1) 🎯 MVP

**Goal**: When the planner builds the month, any weekday that falls on a Hamburg public holiday is created in a not-included state (hours = 0, excluded from the submission batch), so the user never accidentally books work hours on a public holiday (FR-002, FR-005, FR-014 from spec.md).

**Independent Test** (spec § US1): Run `moco-filler --month 2026-05` against an unfilled sandbox month. Without touching any row, confirm that the rows for 2026-05-01 (Tag der Arbeit) and 2026-05-14 (Christi Himmelfahrt) are excluded from the would-be submission batch, while every other weekday in May is included at the normal 8 h default.

### Tests for User Story 1 (Constitution §IV — mandatory) ⚠️

- [X] T015 [P] [US1] In `tests/test_planner.py`, add a test for `build_planned_entries(year, month, activities=[], holiday_catalogue={date(2026, 5, 1): "Tag der Arbeit"})` — assert the resulting list has the 2026-05-01 row with `holiday_name="Tag der Arbeit"`, `included=False`, `hours=Decimal("0")`, `is_submitable == False`, and every OTHER weekday in May 2026 is a normal `planned` row with `hours=Decimal("8")`.
- [X] T016 [P] [US1] In `tests/test_planner.py`, add a test for the FR-005 precedence rule: when a date is BOTH a holiday AND has existing logged hours ≥ 8 h, the resulting row is `already_logged=True`, `holiday_name="Karfreitag"` is preserved (still on the entry), `included=False`. This proves the holiday metadata is kept but the rendering precedence is already-logged.
- [X] T017 [P] [US1] In `tests/test_planner.py`, add a test that calling `build_planned_entries(...)` without the `holiday_catalogue` argument (FR-007 / FR-013 graceful fallback, empty mapping default) produces the same shape as feature 001 — every weekday is a normal `planned` / `top-up` / `already_logged` row, zero rows carry `holiday_name`.

### Implementation for User Story 1

- [X] T018 [US1] In `src/moco_filler/planner.py`, extend the `build_planned_entries` signature with `holiday_catalogue: Mapping[date, str] = {}` and update `_build_one(d, existing_total, holiday_name)` (or thread the catalogue through) so:
  - When `d in holiday_catalogue` AND `existing_total >= DAY_FULL_THRESHOLD` → emit an `already_logged` row with `holiday_name` set (FR-005).
  - When `d in holiday_catalogue` AND `existing_total < DAY_FULL_THRESHOLD` → emit `holiday_name=holiday_catalogue[d]`, `included=False`, `hours=HOURS_FLOOR`, `note=f"Holiday: {holiday_catalogue[d]}"`.
  - Otherwise → existing behaviour unchanged.
- [X] T019 [US1] In `src/moco_filler/cli.py`, import `from moco_filler.holidays import get_hamburg_holidays`; call `holiday_catalogue = get_hamburg_holidays(year)` after `_pick_task(project)` returns and before `client.get_activities(...)`; pass the result as the new fourth argument to `build_planned_entries(year, month, activities, holiday_catalogue)`.
- [ ] T020 [US1] Sandbox check: run `moco-filler --month 2026-05` against a sandbox Moco tenant, confirm 2026-05-01 and 2026-05-14 are NOT included in the submission batch (Approve without editing; the success message should report ~21 entries, not 23). Confirm the FR-015 stderr status line appeared on the first cold-cache run.

**Checkpoint**: US1 ships the MVP — Hamburg holidays are dropped from the submission. The user can already trust the tool not to book hours on a public holiday. US2 adds the visible label so they understand *why*.

---

## Phase 4: User Story 2 — Holiday rows are visibly labelled in the preview (Priority: P1) 🎯 MVP

**Goal**: The preview shows holiday rows in a distinct, recognisable state that names the holiday (FR-003, FR-004). A holiday row is not just a "skipped" row — its State column carries `[holiday: <German name>]` and, when colour is enabled, the row is rendered in a fresh state colour (`row.holiday` — bright magenta) distinct from the four pre-existing row states.

**Independent Test** (spec § US2): Run `moco-filler --month 2026-05`. Confirm that the rows for 2026-05-01 and 2026-05-14 show `[holiday: Tag der Arbeit]` and `[holiday: Christi Himmelfahrt]` in the State column AND are visually distinct from any normal skipped row. Re-run with `NO_COLOR=1 moco-filler --month 2026-05 | tee /tmp/preview.log` and confirm the textual `[holiday: ...]` label is still visible in the plain output.

### Tests for User Story 2 (Constitution §IV — mandatory) ⚠️

- [X] T021 [P] [US2] In `tests/test_preview_logic.py`, add a test for the existing `state_label(entry)` helper (or `format_row` if labels are inlined there): a holiday row (`holiday_name="Karfreitag"`, `already_logged=False`, `included=False`) → returns a string containing `[holiday: Karfreitag]`. A holiday + already-logged row (FR-005) still returns the `[already logged]` label, not the holiday one. An overridden holiday row (`holiday_name="Karfreitag"`, `included=True`) renders WITHOUT the `[holiday: ...]` label (because it is no longer the auto-skip reason — FR-006).
- [X] T022 [P] [US2] In `tests/test_styling.py`, add a test for `build_style()` that asserts the assembled `prompt_toolkit.styles.Style` carries a `row.holiday` rule (use `style.style_rules` or the same shape used by the existing US2 styling tests in feature 002 to assert key presence).
- [X] T023 [P] [US2] In `tests/test_styling.py`, add a test for `format_styled_row(entry)` on a holiday row: with colour enabled, returns `[("class:row.holiday", "<formatted row text>")]`; with colour disabled, returns the same plain string `preview.format_row(entry)` would produce. Update the existing four-state dispatch test (if it asserts exhaustiveness) to expect five branches now.

### Implementation for User Story 2

- [X] T024 [US2] In `src/moco_filler/preview.py`, update the State-column label helper (`state_label(entry)` or wherever the trailing bracket label is built) so the dispatch order is: `already_logged` → `[already logged]`; `holiday_name and not included` → `[holiday: <name>]`; `not included` → `[skipped]`; `existing_hours_total > 0` → `[top-up: existing <h>h]`; default → `""` (planned row, no trailing label). The five conditions are mutually exclusive and exhaustive per `research.md` §9.
- [X] T025 [US2] In `src/moco_filler/styling.py`, extend `build_style()`'s `Style.from_dict` mapping with one new entry: `"row.holiday": "fg:#d75fd7 bold"` (bright magenta — the only ANSI primary not yet used by features 001 / 002, per `research.md` §10). No other style class is renamed or repurposed.
- [X] T026 [US2] In `src/moco_filler/styling.py`, extend `format_styled_row(entry)`'s state-dispatch table with the new branch: `entry.holiday_name and not entry.already_logged and not entry.included` → `("class:row.holiday", text)`. Place this branch BEFORE the existing `included=False → row.skipped` branch so the holiday auto-skip wins over the generic skipped state (FR-003 distinguishability).
- [ ] T027 [US2] Sandbox check: run `moco-filler --month 2026-05` and visually confirm 2026-05-01 + 2026-05-14 read `[holiday: Tag der Arbeit]` / `[holiday: Christi Himmelfahrt]` in magenta, distinct from any other row's colour. Then run `NO_COLOR=1 moco-filler --month 2026-05 | tee /tmp/preview.log` and `grep -E $'\\x1b' /tmp/preview.log` — confirm zero escape-sequence hits AND the textual `[holiday: ...]` label is still in `/tmp/preview.log` (FR-008 / SC-005).

**Checkpoint**: US2 closes the MVP. Holiday rows are auto-skipped (US1) AND clearly labelled (US2). The user knows *why* every day was left out.

---

## Phase 5: User Story 3 — Override an auto-skipped holiday (Priority: P3)

**Goal**: A user who actually worked on a public holiday can still book hours via the existing per-row sub-menu (`Include` / `Change hours`), and a later `Skip` on the same row restores the canonical holiday-skipped state (FR-006, FR-007). The override is deliberate; the default remains skipped.

**Independent Test** (spec § US3): Open the preview for May 2026, navigate to the 2026-05-01 row, open the sub-menu, choose `Include`. Confirm the row turns into a normal included row (no `[holiday: ...]` label, included in the would-be submission). Then `Skip` the same row again. Confirm the row returns to the holiday auto-skip state with `[holiday: Tag der Arbeit]` visible.

### Tests for User Story 3 (Constitution §IV — mandatory) ⚠️

- [X] T028 [P] [US3] In `tests/test_planner.py`, add a test for `toggle_skipped(row)` on a holiday row (`holiday_name="Tag der Arbeit"`, `included=False`, `hours=Decimal("0")`): the result MUST have `included=True`, `holiday_name="Tag der Arbeit"` preserved, and `hours` restored to a positive default (the existing `HOURS_CAP` if no other state, matching the spec's "becomes submitable at the same default hours as any other re-included row" wording in US3 AC-1).
- [X] T029 [P] [US3] In `tests/test_planner.py`, add a test for `toggle_skipped(row)` on a re-included holiday row (`holiday_name="Tag der Arbeit"`, `included=True`, `hours=Decimal("8")`): the result MUST have `included=False`, `holiday_name="Tag der Arbeit"` preserved, and `hours=Decimal("0")` (FR-007 — canonical holiday-skip state restored, not a generic user skip).
- [X] T030 [P] [US3] In `tests/test_planner.py`, add a test that `toggle_skipped(row)` on an already-logged + holiday row STILL raises `ValueError` per the existing FR-012 lock from feature 001 (the holiday metadata does not change the lock semantics).

### Implementation for User Story 3

- [X] T031 [US3] In `src/moco_filler/planner.py`, update `toggle_skipped(row)` so that when toggling from `included=True` → `included=False` on a row whose `holiday_name is not None`, `hours` is also reset to `HOURS_FLOOR` (so the row returns to the canonical auto-skipped shape, matching the shape `build_planned_entries` would have produced fresh). When toggling from `included=False` → `included=True` on a holiday row, restore `hours` to `HOURS_CAP` (or to `HOURS_CAP - existing_hours_total` if `existing_hours_total > 0`, matching the top-up rule from feature 001). The `dataclasses.replace` call already preserves `holiday_name` because it copies unmentioned fields — no extra work needed for the metadata.
- [ ] T032 [US3] Sandbox check: in `moco-filler --month 2026-05`, navigate to the 2026-05-01 row, sub-menu → `Include`, return to preview, confirm the row now has no `[holiday: ...]` label and 8.00h. Then navigate back, sub-menu → `Skip`, confirm the row returns to `[holiday: Tag der Arbeit]` with 0.00h. Approve. Confirm 2026-05-01 is NOT in the submission batch (because we Skipped it again).

**Checkpoint**: All three user stories are independently functional. The MVP shipped in US1+US2; US3 adds the override loop for the rare overtime case.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T033 [P] Update `README.md` to mention: (a) the new auto-skip-on-Hamburg-holidays behaviour, (b) the per-OS cache file location, (c) how to force a refresh by deleting the cache file. Keep it brief — the full reference is `specs/004-cache-holidays-locally/quickstart.md`.
- [X] T034 [P] Run the full test suite (`pytest`) from the repo root and confirm 100% of the pre-existing tests still pass (SC-007 — no behavioural regression in feature 001 / 002 paths).
- [ ] T035 Perform the `quickstart.md` end-to-end smoke check: (a) cold-cache run shows the stderr status line and creates `holidays.json`; (b) warm-cache run is silent on stderr; (c) offline run with a populated cache still shows holiday rows; (d) offline run with the cache file deleted shows the FR-007 fallback (no holiday rows marked, no error). SC-001 through SC-007 all green.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)** and **Foundational (Phase 2)**: Setup is empty; Foundational lands the `holidays` module + the `PlannedEntry.holiday_name` field. Both US1 and US2 depend on Foundational.
- **US1 (Phase 3)**: depends on Foundational. Adds the planner consumption + CLI wiring.
- **US2 (Phase 4)**: depends on Foundational. Adds the preview render + the styling token. Can technically start in parallel with US1 (different files) but is most cleanly sequenced after US1 so the sandbox checks build on each other.
- **US3 (Phase 5)**: depends on US1 (toggle_skipped behaviour change builds on the planner extension). Independent of US2 in code but the sandbox check uses US2's visible label.
- **Polish (Phase 6)**: depends on US1 + US2 + US3.

### Within-story dependencies

- **Foundational**: T001 / T002 / T003 / T004 / T005 / T006 / T007 are [P] across `tests/test_models.py` and the new `tests/test_holidays.py` — write them all up front. T008 is independent of T009–T014 (different file). T009 → T010 → T011 → T012 → T013 → T014 are sequential by file (all in `holidays.py`) and by call graph (T014 calls T011 + T013, which call T010 + T012).
- **US1**: T015 / T016 / T017 are [P] in `tests/test_planner.py` (different test functions, same file — write together TDD-style). T018 (planner.py) and T019 (cli.py) are different files — [P]-able but T019 doesn't compile until T018 lands. Run T018 → T019. T020 is the sandbox check, last.
- **US2**: T021 (test_preview_logic.py) / T022 / T023 (test_styling.py) are [P] across two test files. T024 (preview.py) is independent of T025 + T026 (styling.py) — [P]-able by file. T025 → T026 sequential by file. T027 sandbox last.
- **US3**: T028 / T029 / T030 are [P] in `tests/test_planner.py`. T031 is a single-file change in `planner.py`. T032 sandbox last.
- **Polish**: T033 / T034 are [P] across `README.md` and pytest. T035 is the final manual gate.

### Parallel opportunities

- All `[P]` test tasks within a phase can be written together.
- US1 and US2 can be split across two developers in parallel after Foundational completes (US1 touches planner.py + cli.py, US2 touches preview.py + styling.py — disjoint sets of files).
- US3 cannot start until US1 lands (`toggle_skipped` semantics depend on the new `holiday_name` field being honoured by the planner).

---

## Parallel Example: kicking off Foundational

```bash
# Write the test scaffolds in parallel first (TDD per Constitution §IV):
Task: "Add holiday_name default test to tests/test_models.py"                       # T001
Task: "Add _cache_path() per-OS tests to tests/test_holidays.py"                    # T002
Task: "Add _load_cache() miss-modes tests to tests/test_holidays.py"                # T003
Task: "Add _save_cache() round-trip tests to tests/test_holidays.py"                # T004
Task: "Add _validate_response() shape + Hamburg filter tests to tests/test_holidays.py"  # T005
Task: "Add _fetch_with_retry() budget + attempts tests to tests/test_holidays.py"   # T006
Task: "Add get_hamburg_holidays() orchestration tests to tests/test_holidays.py"    # T007

# Then implement the model + scaffold the new module in parallel:
Task: "Add holiday_name optional field to src/moco_filler/models.py"                # T008
Task: "Create src/moco_filler/holidays.py with _cache_path()"                       # T009
```

---

## Parallel Example: US1 + US2 across two developers

After Foundational lands, two developers can run in parallel:

```bash
# Developer A — US1 (planner + cli)
T015 → T016 → T017                  # tests in tests/test_planner.py
T018                                 # planner.py extension
T019                                 # cli.py wiring
T020                                 # sandbox check

# Developer B — US2 (preview + styling)
T021                                 # tests in tests/test_preview_logic.py
T022 → T023                          # tests in tests/test_styling.py
T024                                 # preview.py label dispatch
T025 → T026                          # styling.py palette + dispatch
T027                                 # sandbox check
```

US3 starts once US1 is merged (T031 builds on T018's PlannedEntry construction shape).

---

## Implementation Strategy

### MVP first (US1 + US2 together)

Both US1 and US2 are P1 in spec.md — they ship together. The user's
ask was "skip those days AND show them as holidays" in one breath.
The plan is:

1. Complete Phase 1 (empty) and Phase 2 (Foundational) — the
   `holidays` module + model field.
2. Complete Phase 3 (US1) — auto-skip in the planner.
3. Complete Phase 4 (US2) — the visible holiday label in the
   preview.
4. **Stop and validate** against US1 + US2 Independent Tests
   (T020 + T027).
5. Demo / ship — the user can now trust the tool to handle Hamburg
   holidays end-to-end.

### Incremental delivery

1. Foundational lands (cache + fetch wired up but not yet consumed
   anywhere — the CLI still ignores holidays). Tests green.
2. US1 lands (the planner now consumes the catalogue; holidays are
   silently dropped from the submission but the preview doesn't
   highlight them yet). Demoable to a tester who reads the
   would-be-submitted list.
3. US2 lands (holidays are now both dropped AND visibly labelled
   in the preview). MVP ships.
4. US3 lands (override). Edge-case completeness.
5. Polish (Phase 6) gates the merge to `main`.

### Solo developer rhythm

Stories run sequentially (Foundational → US1 → US2 → US3 → Polish),
each producing a chain of small commits (one per task, or one per
TDD test+impl pair as in feature 002) that satisfy Constitution
§II. Don't open US1 before Foundational's checkpoint passes.

---

## Notes

- **No new top-level dependencies** — `requests` is already shipped via `moco_client.py`; the new `holidays.py` reuses it. If a task seems to need a new package (`python-holidays`, `platformdirs`, `backoff`, etc.), stop and re-read `research.md` §§1, 2, 5.
- **No live network in tests** — every `holidays.py` test that exercises the fetch path uses an injected fake `Session`. The real `date.nager.at` endpoint is never contacted by `pytest`. The sandbox checks (T020, T027, T032, T035) are the only paths that touch the live source.
- **Commit message rule** — per Constitution §II + the 1.1.0 amendment, every commit MUST explain *why* in the subject line (when it fits) or in a body paragraph. Bake the "why" into each task's commit before moving on.
- **`PlannedEntry.holiday_name` defaults to `None`** — existing tests and existing planner code paths construct rows without the new field; the `None` default keeps them working unchanged. No migration shim needed.
- **FR-015 stderr status line** — emitted only by `get_hamburg_holidays` on a cold-cache miss. Tests assert it via `capsys.readouterr().err`. The stdout-scrape contract from feature 001 (`specs/001-create-mvp-moco-filler-app/contracts/cli.md`) is untouched.
- **Sandbox tasks (T020, T027, T032, T035)** require a real Moco sandbox key and a real terminal — they cannot be executed by an automated agent. They are the human gate before merge.
- **Cache file inspection** — see `quickstart.md` § Inspecting the cache. The file is plain JSON, safe to `cat`, contains nothing sensitive (FR-009 / contract).
