# Quickstart: Table-Styled Preview

**Feature**: 002-add-coloring-and-spacing-to-the-app

**Date**: 2026-06-01

This feature is a presentation refinement of the existing
`moco-filler` CLI. The install + run workflow from
[`specs/001-create-mvp-moco-filler-app/quickstart.md`](../001-create-mvp-moco-filler-app/quickstart.md)
is unchanged — only what you see on screen differs.

---

## 1. Run it (no flags changed)

```bash
source .venv/bin/activate
export MOCO_API_KEY="<your sandbox key>"
moco-filler --month 2026-06
```

What's different from feature 001:

- The preview now opens with a header row labelling each column.
- Each data row is colour-coded by state (planned / top-up /
  already-logged / skipped).
- The focused row carries a `▶` marker and a reverse-video
  background so the cursor is unmistakable.
- The `Approve & submit` / `Cancel` actions are green and red
  respectively.

---

## 2. Turn colour off

The CLI follows the cross-platform `NO_COLOR` convention. Either of
these renders the table in plain monochrome without changing any
other behaviour:

```bash
NO_COLOR=1 moco-filler --month 2026-06
moco-filler --month 2026-06 | tee preview.log     # piped → monochrome
moco-filler --month 2026-06 2>&1 | grep something  # non-TTY → monochrome
TERM=dumb moco-filler --month 2026-06              # explicitly dumb terminal
```

When colour is off:

- Column alignment is preserved.
- No raw escape sequences appear in the captured output.
- Questionary still draws its default pointer glyph (`»`) on the
  focused row so navigation remains usable.

---

## 3. Where the palette lives

If you want to tune the colours, the single source of truth is the
`build_style()` factory in `src/moco_filler/styling.py`. The
prompt_toolkit `Style.from_dict` mapping there is the only place
colour values are defined; everything else refers to style class
names (`row.planned`, `row.topup`, `row.locked`, `row.skipped`,
`action.approve`, `action.cancel`, `pointer`, `highlighted`, …).

Editing the dict is the entire change required to ship an alternate
palette — `preview.py` does not need to be touched.

---

## 4. Smoke-checking the change

After installing the feature branch:

1. **Header alignment**: open the preview. Visually confirm that the
   `D` in `Date` (header) is in the same screen column as the `2` in
   `2026-06-03` (first data row).
2. **State colours**: pick a month where one date is already at 8h
   in Moco, one date is a partial top-up, and the rest are empty.
   Confirm three visually distinct colours appear in the preview
   without reading the trailing label.
3. **Cursor visibility**: press the down-arrow once. Confirm exactly
   one row is now visually distinct from every other row.
4. **NO_COLOR fallback**: run with `NO_COLOR=1 moco-filler --month
   YYYY-MM`. Confirm the header still aligns, no escape codes leak
   to the terminal, and navigation still works.
5. **Behaviour parity**: edit a row's hours and approve. Confirm
   Moco creates the entry with the edited hours — exactly the same
   behaviour as before this feature.
6. **Regression**: `pytest`. All pre-existing tests still pass
   (SC-006).

---

## 5. What did NOT change

- The CLI flag set (`--month YYYY-MM` only).
- The exit codes (0 / 1 / 2 / 3 / 4 / 5 / 6 / 7 — see feature 001's
  `contracts/cli.md`).
- The four stdout summary lines.
- The `MOCO_API_KEY` env var contract (still in-memory only, never
  written to disk per FR-001).
- Any HTTP behaviour against the Moco API.
- The `PlannedEntry` / `SubmissionBatch` / `SubmissionResult`
  dataclasses.

If something in this list looks different on the feature branch,
that is a regression and should block the merge.
