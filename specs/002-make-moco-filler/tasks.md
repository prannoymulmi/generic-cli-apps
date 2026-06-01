# Tasks: Table-Styled Preview for moco-filler

**Input**: Design documents from `/specs/002-make-moco-filler/`

**Branch**: `002-make-moco-filler`

**Date**: 2026-06-01

**Tests**: Unit tests are MANDATORY per Constitution §IV (Unit Tests Only — non-negotiable). Each story's implementation tasks are paired with the unit-test tasks that cover their pure helpers. The live Questionary preview loop is intentionally not unit-tested (per `specs/001-moco-time-tracker/research.md` §8 and `research.md` §8); the helpers extracted from it are.

**Organization**: Tasks are grouped by user story so each story can be implemented, committed, and tested as an independent atomic increment per Constitution §II.

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel — different files, no incomplete dependencies.
- **[Story]**: Required for user-story phases (US1, US2, US3); omitted in Setup, Foundational, and Polish phases.

## Path Conventions

Single-project layout from `plan.md` → "Project Structure":

- Source: `src/moco_filler/`
- Tests: `tests/`

No new dependencies, no new packages — this feature is presentation-only on top of feature 001.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Nothing new — the package skeleton, `pyproject.toml`, `.gitignore`, `requirements.txt`, and pytest configuration are already present from feature 001 and the feature does not add a new top-level dependency (FR-009).

*This phase is intentionally empty for feature 002.*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Nothing blocks user-story work. US1 is pure layout (no new module). US2 and US3 each introduce / extend `styling.py` in their own phase. There are no shared prerequisites beyond what feature 001 already shipped.

*This phase is intentionally empty for feature 002.*

---

## Phase 3: User Story 1 — Column-aligned table with header (Priority: P1) 🎯 MVP

**Goal**: Repaint the preview as a real table — a header row labelling `Day` / `Date` / `Hours` / `State` and every data row aligned beneath it (FR-001, FR-002, FR-003). Monochrome only at this stage; colour layers land in US2 / US3.

**Independent Test** (spec § US1): Run `moco-filler` against an empty sandbox month. Confirm the preview shows a header row whose columns line up with every data row; resize the terminal to 80 columns and confirm the alignment holds.

### Tests for User Story 1 (Constitution §IV — mandatory) ⚠️

> Per Constitution §IV, write each test alongside or before its implementation. Don't merge untested code.

- [ ] T001 [P] [US1] Extend `tests/test_preview_logic.py` with column-alignment tests for `format_row` (Day=3, Date=10, Hours=5, State=flex; 2-space gaps per `contracts/preview-rendering.md` § Column layout): assert every f-string field is the right width and that the screen column of the `[` opening bracket of the State label is identical across plain / top-up / locked / skipped rows.
- [ ] T002 [P] [US1] Extend `tests/test_preview_logic.py` with a test for the new `format_header()` helper — asserting it returns a single line whose `Day` / `Date` / `Hours` / `State` labels start at the same screen columns produced by `format_row()` (the "vertical alignment under the header" invariant from FR-002).
- [ ] T003 [P] [US1] Extend `tests/test_preview_logic.py` with a test for `_build_choices()` proving the first emitted element is a `questionary.Separator` carrying the header text (US1.AC-1: header sits directly above the data rows).

### Implementation for User Story 1

- [ ] T004 [US1] In `src/moco_filler/preview.py`, update `format_row(entry)` to emit a column-aligned plain string using fixed widths (Day=3 left, Date=10 left, Hours=5 right, State=flex left) and two-space gaps. Keep the existing positional signature unchanged so `tests/test_preview_logic.py`'s existing assertions still pass (per `research.md` §7 — option (a)).
- [ ] T005 [US1] In `src/moco_filler/preview.py`, add `format_header() -> str` returning the matching header line (`"Day  Date         Hours  State"` in monochrome). Place it next to `format_row` and `state_label` to keep all pure formatters in one place (Constitution §V).
- [ ] T006 [US1] In `src/moco_filler/preview.py`, modify `_build_choices(entries)` to prepend a `questionary.Separator(format_header())` as the first item, so every preview repaint shows the header anchored above the data rows.
- [ ] T007 [US1] Run the US1 independent test against a sandbox account per `quickstart.md` §4 step 1 — confirm header alignment by eye on an empty month, and re-run on a month with partial / locked / skipped rows to confirm the columns still line up.

**Checkpoint**: US1 ships the MVP — a clean monochrome table with a labelled header. The CLI is already more readable; US2 and US3 add the colour layers.

---

## Phase 4: User Story 2 — Per-state colour coding (Priority: P2)

**Goal**: Each row state (planned / top-up / already-logged / skipped) is rendered in its own colour when the terminal supports it; `NO_COLOR=1`, non-TTY stdout, or `TERM=dumb` falls back to clean monochrome (FR-005, FR-007). The styling extends to the project picker, the task picker, AND the per-row sub-menu (FR-008a per the 2026-06-01 clarification).

**Independent Test** (spec § US2): Open the preview on a month where one date is at 8h, one is a partial top-up, and the rest are empty. Confirm the three states are visually distinct without reading the trailing label. Then re-run with `NO_COLOR=1` and confirm zero escape sequences leak when piping to `tee preview.log`.

### Tests for User Story 2 (Constitution §IV — mandatory) ⚠️

- [ ] T008 [P] [US2] Create `tests/test_styling.py` covering `is_color_enabled()` across all four trigger combinations: no env / `NO_COLOR=1` / `sys.stdout.isatty() == False` (monkeypatch) / `TERM=dumb`. Use `monkeypatch.setenv` and `monkeypatch.setattr(sys, 'stdout', ...)` so the test is hermetic.
- [ ] T009 [P] [US2] In `tests/test_styling.py`, add tests for `build_style()`: returns `None` when colour disabled; returns a `prompt_toolkit.styles.Style` instance when colour enabled (assert via `isinstance` only — the exact RGB values are tunable per the contract).
- [ ] T010 [P] [US2] In `tests/test_styling.py`, add tests for `format_styled_row(entry)` per-state class dispatch: a plain row → `("class:row.planned", text)`; a top-up row → `("class:row.topup", text)`; a locked row → `("class:row.locked", text)`; a skipped row → `("class:row.skipped", text)`. Use the same `_plain` / `_top_up` / `_locked` / `_skipped` helper-row pattern that `tests/test_preview_logic.py` already uses.

### Implementation for User Story 2

- [ ] T011 [US2] Create `src/moco_filler/styling.py` with `is_color_enabled() -> bool` implementing the three-branch predicate from `research.md` §3 — returns `False` on non-empty `NO_COLOR`, non-TTY stdout, or `TERM=="dumb"`, `True` otherwise. Imports only `os` and `sys`.
- [ ] T012 [US2] In `src/moco_filler/styling.py`, add `build_style() -> Optional[Style]` that returns `None` when `is_color_enabled()` is `False`, otherwise returns a `prompt_toolkit.styles.Style.from_dict({...})` carrying the four `row.*` classes from `contracts/preview-rendering.md` § Colour palette (`row.planned`, `row.topup`, `row.locked`, `row.skipped`, plus `row.header`). Action and chrome classes are added in US3.
- [ ] T013 [US2] In `src/moco_filler/styling.py`, add `format_styled_row(entry: PlannedEntry) -> list[tuple[str, str]] | str` that dispatches on `(already_logged, included, existing_hours_total > 0)` to pick one of `row.planned` / `row.topup` / `row.locked` / `row.skipped`, returning a `[(class, text)]` FormattedText list when colour is enabled and the plain `preview.format_row(entry)` string otherwise. Reuse `preview.format_row` for the text content (single source of truth per `research.md` §1).
- [ ] T014 [US2] In `src/moco_filler/styling.py`, add `format_styled_header() -> list[tuple[str, str]] | str` mirroring `preview.format_header()` but wrapped in `("class:row.header", text)` when colour is enabled.
- [ ] T015 [US2] In `src/moco_filler/preview.py`, update `_build_choices(entries)` so each data-row `Choice.title` becomes `format_styled_row(entry)` (the new helper) and the leading `Separator` uses `format_styled_header()`. Keep the monochrome path identical to US1's output.
- [ ] T016 [US2] In `src/moco_filler/preview.py`, update `_edit_row` so its sub-menu prompt strings render the same row through `format_styled_row(row)` instead of `format_row(row)` — i.e. the per-row sub-menu (`Skip` / `Include` / `Change hours` / `Back`) shows the same coloured row at the top of the sub-prompt (FR-008a, clarification 2026-06-01).
- [ ] T017 [US2] In `src/moco_filler/cli.py`, replace the project picker's choice titles with the styled-row equivalent of the project name (one styled `Choice` per project) and do the same for the task picker, so all selection screens share the colour vocabulary defined in `styling.py` (FR-008a).
- [ ] T018 [US2] Verify the `NO_COLOR` fallback per `quickstart.md` §2: run `NO_COLOR=1 moco-filler --month 2026-06 | tee /tmp/preview.log`, then `grep -E $'\\x1b' /tmp/preview.log` and confirm zero hits (SC-004).

**Checkpoint**: US2 ships per-state colour across every interactive screen in one run. The cursor is still drawn by Questionary's defaults; US3 makes the cursor unmistakable.

---

## Phase 5: User Story 3 — Visible cursor + styled actions (Priority: P2)

**Goal**: The focused row is unmistakable — a left-edge `▶` marker AND a reverse-video text background — and the `Approve & submit` / `Cancel` actions carry distinct colours (FR-004, FR-006). All of this extends to the pickers + sub-menu (FR-008a).

**Independent Test** (spec § US3): Open the preview and arrow up/down. At every step exactly one row is marked focused, and pressing Enter on the marked row opens the sub-menu for that exact row (no off-by-one). The `Approve & submit` choice reads green; `Cancel` reads red.

### Tests for User Story 3 (Constitution §IV — mandatory) ⚠️

- [ ] T019 [P] [US3] In `tests/test_styling.py`, add tests for `build_style()` (colour-enabled mode) declaring keys for `pointer`, `highlighted`, `qmark`, `instruction`, `selected`, `separator`, `action.approve`, `action.cancel`. Use the prompt_toolkit `Style.from_dict` interface (`style.style_rules` or `style.invalidation_hash()` is acceptable) to assert each class is present.
- [ ] T020 [P] [US3] In `tests/test_styling.py`, add tests for `format_action(label, kind)`: returns `("class:action.approve", label)` for `kind="approve"`, `("class:action.cancel", label)` for `kind="cancel"`, and the plain `label` string when colour is disabled.

### Implementation for User Story 3

- [ ] T021 [US3] In `src/moco_filler/styling.py`, extend `build_style()`'s `Style.from_dict` mapping with the chrome classes from `contracts/preview-rendering.md` § Colour palette: `pointer` (bright green bold), `highlighted` (reverse), `qmark`, `instruction`, `selected`, `separator`, plus the two action classes `action.approve` (bright green bold) and `action.cancel` (bright red bold).
- [ ] T022 [US3] In `src/moco_filler/styling.py`, add `format_action(label: str, kind: Literal["approve", "cancel"]) -> list[tuple[str, str]] | str` returning `[(f"class:action.{kind}", label)]` when colour is enabled, the plain `label` otherwise.
- [ ] T023 [US3] In `src/moco_filler/styling.py`, add a `POINTER_GLYPH = "▶ "` module-level constant and a `get_style() -> Optional[Style]` lazy accessor that builds the `Style` once and caches it (per `plan.md` § Project Structure rationale — avoid threading `Style` through every function).
- [ ] T024 [US3] In `src/moco_filler/preview.py`, update `_build_choices` so the `✅ Approve & submit` and `❌ Cancel` `Choice.title`s use `format_action(label, "approve")` / `format_action(label, "cancel")`. Pass `style=get_style()` to every `questionary.select` and `questionary.text` call in the file (main preview, sub-menu, locked-row Back-only, hours prompt). When `get_style()` is `None`, omit the `style=` kwarg entirely so the monochrome path stays clean (no `style=None` leaks).
- [ ] T025 [US3] In `src/moco_filler/cli.py`, pass `style=get_style()` to both `questionary.select` calls in `_pick_project` and `_pick_task` (FR-008a) — same `None` handling as in T024.
- [ ] T026 [US3] In `src/moco_filler/preview.py` / `src/moco_filler/cli.py`, set Questionary's pointer glyph to the `▶` defined in `styling.POINTER_GLYPH` (via the appropriate Questionary parameter — typically the `style` dict's `pointer` class drives both colour and glyph in prompt_toolkit's `select` widget; if Questionary needs an explicit `pointer=` keyword, pass it from `styling.POINTER_GLYPH`). When colour is disabled, do NOT override the glyph (Questionary's default stays per the contract).
- [ ] T027 [US3] Run the US3 independent test against a sandbox account per `quickstart.md` §4 steps 2–3 — arrow up/down through every row and confirm exactly one row is marked focused at any moment, including when the focus lands on an already-logged (dim grey) row. Confirm `Approve` and `Cancel` are visibly distinct.

**Checkpoint**: All three user stories are independently functional. The preview is a real terminal table with colour, a header row, and an unmistakable cursor.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T028 [P] Update `README.md` to mention the `NO_COLOR=1` opt-out for monochrome output (so a casual reader doesn't have to dig through `specs/002-make-moco-filler/quickstart.md`).
- [ ] T029 [P] Run the full test suite (`pytest`) from the repo root and confirm 100% of the pre-existing tests still pass (SC-006 — no behavioural regression).
- [ ] T030 Perform the `quickstart.md` §4 smoke check end to end: header alignment, three distinct state colours, cursor visible on every row state, `NO_COLOR=1` produces clean monochrome, an edit-and-approve round trip produces the same Moco entries as feature 001 (SC-001 through SC-006).

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)** and **Foundational (Phase 2)**: empty for this feature.
- **US1 (Phase 3)**: no dependencies — pure `preview.py` changes. MVP.
- **US2 (Phase 4)**: depends on US1's `format_row` / `format_header` (T013 / T014 import them).
- **US3 (Phase 5)**: depends on US2's `styling.py` (T021 extends `build_style()`, T024–T026 thread the `Style` and pointer through every Questionary call site).
- **Polish (Phase 6)**: depends on US1 + US2 + US3.

### Within-story dependencies

- **US1**: T001 / T002 / T003 are [P] tests across the same test file but independent assertions (can be written together). T004 → T005 → T006 (sequential, all touch `preview.py`). T007 last.
- **US2**: T008 / T009 / T010 are [P] in `tests/test_styling.py` (different test functions, same file — write them together TDD-style). T011 → T012 → T013 / T014 (T013 and T014 are both in `styling.py` but [P]-able by function). T015 → T016 (`preview.py`, sequential). T017 (`cli.py`, [P] with T015 / T016). T018 (sandbox check) last.
- **US3**: T019 / T020 [P] in tests. T021 → T022 → T023 (all `styling.py`, sequential by file). T024 → T026 (`preview.py`). T025 (`cli.py`, [P] with T024).

### Parallel opportunities

- All `[P]` test tasks within a phase can be written together (different test functions, same or different files).
- US2 and US3 implementation cannot be parallelised: US3's chrome lives in the same `build_style()` that US2 introduces, so it builds on top.

---

## Parallel Example: kicking off User Story 2

```bash
# Write the test scaffolds in parallel first (TDD per Constitution §IV):
Task: "Test is_color_enabled() across four triggers in tests/test_styling.py"  # T008
Task: "Test build_style() returns Optional[Style] in tests/test_styling.py"     # T009
Task: "Test format_styled_row() per-state class dispatch"                       # T010

# Then implement the two file-independent helpers in parallel:
Task: "Add format_styled_row() to styling.py"                                   # T013
Task: "Add format_styled_header() to styling.py"                                # T014
```

---

## Implementation Strategy

### MVP first (US1 only)

1. Skip Phase 1 + Phase 2 (empty).
2. Finish Phase 3: US1.
3. **Stop and validate** against US1's Independent Test (T007).
4. The preview is now a clean monochrome table. Demo if useful.

### Incremental delivery

1. Ship US1 (above).
2. Add US2 → re-run US2's Independent Test (T018). State is now colour-coded; `NO_COLOR` still produces clean output.
3. Add US3 → re-run US3's Independent Test (T027). v1 feature-complete.
4. Polish (Phase 6) gates the final tag.

### Solo developer rhythm

Stories run sequentially (US1 → US2 → US3), each producing a chain of small commits (one per task, or one per TDD test+impl pair as in feature 001) that satisfy Constitution §II. Don't open US2 before US1's checkpoint passes.

---

## Notes

- **No new dependencies** — this feature uses only Questionary symbols already shipped (FR-009). If a task seems to need `rich` / `textual` / `colorama`, stop and re-read `research.md` §1 + §2.
- **Commit message rule** — per Constitution §II + the 1.1.0 amendment, every commit MUST explain *why* in the subject line (when it fits) or in a body paragraph. Bake the "why" into each task's commit before moving on.
- **`format_row` keeps its signature** — feature 001's `tests/test_preview_logic.py` calls `format_row(entry)` positionally with no kwargs; T004 changes the output to columnar but keeps the signature so existing assertions stay green (per `research.md` §7 option (a)).
- **No code-path leaks of `style=None`** — when `get_style()` returns `None` (colour disabled), call sites MUST omit the `style=` kwarg entirely. Passing `style=None` to Questionary works today but is fragile across versions; defensive omit per `contracts/preview-rendering.md` § Monochrome fallback.
- **Sandbox tasks (T007, T018, T027, T030)** require a real Moco sandbox key and a real terminal — they cannot be executed by an automated agent. They are the human gate before merge.
