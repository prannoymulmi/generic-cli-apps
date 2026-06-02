# Implementation Plan: Table-Styled Preview for moco-filler

**Branch**: `002-add-coloring-and-spacing-to-the-app` | **Date**: 2026-06-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-add-coloring-and-spacing-to-the-app/spec.md`

## Summary

Repaint the existing moco-filler preview as a real terminal table — a
header row labelling `Day` / `Date` / `Hours` / `State`, every data row
aligned beneath it, the four row states (planned / top-up /
already-logged / skipped) coloured distinctly, and the focused row
carrying a left-edge marker plus a contrasting background so the cursor
is never lost. The change is presentation-only: the planner, HTTP
client, models, exit codes, and stdout-scrape contract from
`specs/001-create-mvp-moco-filler-app/contracts/cli.md` are untouched.

Per Constitution §I we stay on Questionary; no `rich`, `textual`, or
direct `curses` is introduced. The visual upgrade rides on two
mechanisms Questionary already exposes — its `style=` parameter (a
prompt_toolkit `Style.from_dict`) for chrome (pointer / highlighted /
qmark / separator) and its FormattedText-style `(class, text)` tuples
for per-row class assignment in `Choice.title`. A small new
`styling.py` module owns the palette, the `NO_COLOR` / non-TTY
detection, and the row-formatter so `preview.py` stays a thin
orchestration layer (Constitution §V). See
[`research.md`](./research.md) for the decisions behind each of these
choices.

## Technical Context

**Language/Version**: Python 3.11 (already pinned in `pyproject.toml`
from feature 001; ≥ 3.9 per constitution).

**Primary Dependencies**:

- `questionary` (already shipped) — every interactive prompt. The
  `style=` argument and FormattedText choice titles are the *only* new
  Questionary surface this feature touches; both ship with the version
  we already pin.
- `prompt_toolkit` (transitively via `questionary`) — `Style.from_dict`
  for the palette definition. No new top-level dependency is added.
- Standard library only for color detection (`os`, `sys`).

**Dev Dependencies**: unchanged — `pytest` covers the new pure helpers.

**Storage**: none — purely in-memory styling state.

**Testing**: `pytest`. New unit tests for the styling module (palette
selection, NO_COLOR / non-TTY fallback, row tuple shape). The live
Questionary loop is still not unit-tested (per the §IV carve-out in
`specs/001-create-mvp-moco-filler-app/research.md` §8).

**Target Platform**: macOS / Linux terminal — same as feature 001.
Color requires an attached TTY that does not opt out via `NO_COLOR`;
otherwise the table renders in monochrome with column alignment intact.

**Project Type**: Single CLI application — same Python package, no
client / server split.

**Performance Goals**: human-interactive scale. Per SC-005 the styling
overhead must not add more than 100ms to a happy-path run. In practice
the styling is per-line f-string formatting plus one `Style.from_dict`
build, so this gate is comfortable.

**Constraints**:

- No new top-level dependency (FR-009).
- No change to the stdout-scrape contract (Assumption in `spec.md`).
- Monochrome output MUST contain zero raw escape sequences when
  `NO_COLOR` is set or stdout isn't a TTY (FR-007, SC-004).
- The Questionary-only mandate (Constitution §I) holds.

**Scale/Scope**: ~23 rows per preview, four state colors, one focus
marker — the surface is small enough that all styling can live in one
module.

## Constitution Check

*Re-checked after Phase 1 design — gates still pass.*

| Principle | How this plan satisfies it |
|-----------|----------------------------|
| **I. Python3 & Questionary-First** | All visual changes go through Questionary's existing `style=` parameter and its FormattedText choice titles. No alternative prompt or TUI library is introduced; the prompt_toolkit symbol used (`Style.from_dict`) ships with Questionary already. |
| **II. Atomic Commits** | The styling work decomposes cleanly into atomic commits (styling module + tests; preview wiring + tests; pickers reuse). No "work-in-progress" intermediate states; each commit leaves `pytest` green. |
| **III. Clean Code & Readability** | `styling.py` exposes a small, named API: `build_style()`, `is_color_enabled()`, `format_row()`. Each is single-purpose and type-hinted. No deep nesting; no docstring repetition of code behaviour. |
| **IV. Unit Tests Only** | Color detection, palette construction, the formatted-text row shape, and the column-width math are all pure functions, all unit-testable. Questionary's live select loop continues to be excluded (`research.md` §1 below confirms this). |
| **V. Single Responsibility & Modularity** | `styling.py` owns visuals; `preview.py` stays orchestration; `cli.py` stays glue. The planner / HTTP client / models import nothing from `styling.py` — styling is a UI concern only. |

**Gate result**: PASS. No violations; the `Complexity Tracking` table
below is left empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-add-coloring-and-spacing-to-the-app/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output — styling + NO_COLOR decisions
├── data-model.md        # Phase 1 output — Row presentation (derived view)
├── quickstart.md        # Phase 1 output — how to disable color, where palette lives
├── contracts/
│   └── preview-rendering.md  # Visual contract: header, columns, focus marker, states
├── checklists/
│   └── requirements.md  # Already PASS-ing
├── spec.md              # Feature spec (already accepted)
└── tasks.md             # Phase 2 output — written by /speckit-tasks, NOT here
```

### Source Code (repository root)

The existing `src/moco_filler/` package gains exactly one new file
(`styling.py`) and gets two existing files lightly updated. No layout
move, no rename, no new top-level dependency.

```text
src/
└── moco_filler/
    ├── __init__.py
    ├── __main__.py
    ├── cli.py              # (modified) pass shared style to pickers + preview
    ├── auth.py
    ├── moco_client.py
    ├── calendar_utils.py
    ├── planner.py
    ├── preview.py          # (modified) header separator, FormattedText choices
    ├── styling.py          # (NEW) palette, NO_COLOR detection, row formatter
    ├── models.py
    └── errors.py

tests/
├── test_calendar_utils.py
├── test_planner.py
├── test_models.py
├── test_moco_client.py
├── test_auth.py
├── test_preview_logic.py   # (modified) header + formatted-row assertions
└── test_styling.py         # (NEW) palette + NO_COLOR fallback + row tuples
```

**Structure Decision**: Reuse the single-project layout established by
feature 001. Rationale:

- This feature is a pure-presentation refinement of an existing
  module; introducing a new sub-package would over-structure a roughly
  100-line addition.
- A single new `styling.py` module keeps the visual policy in one
  named place per Constitution §V (Single Responsibility), so future
  changes (palette tweaks, alternate themes) land in exactly one file
  without touching `preview.py`'s orchestration logic.
- The new `tests/test_styling.py` follows the same one-test-per-module
  convention as the existing test files.

## Complexity Tracking

> No constitution violations to justify; this section is intentionally empty.
