# Quickstart: Moco Monthly Time Tracker CLI

**Feature**: 001-create-mvp-moco-filler-app
**Date**: 2026-06-01

This is the smallest "from clone to filled-out month in Moco" path. It
assumes Python 3.9+ on macOS or Linux, and a terminal that supports basic
ANSI styling.

---

## 1. Install

```bash
git clone <repo-url> cli-apps
cd cli-apps
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

This installs the `moco-filler` console script defined in `pyproject.toml`.

---

## 2. Get your Moco API key

1. Sign in to `https://statista.mocoapp.com`.
2. Open your user profile → Personal API Key.
3. Copy it. You'll either paste it once into the CLI's masked prompt or
   export it as an env var for the session:

   ```bash
   export MOCO_API_KEY="paste-your-key-here"
   ```

   The CLI **never writes this value to disk** (FR-001, SC-004).

---

## 3. Fill the current month

```bash
moco-filler
```

What you'll see (happy path):

1. (Only if `MOCO_API_KEY` is unset) A masked prompt for your API key.
2. A project picker — navigate with ↑/↓, press Enter to choose.
3. A task picker — defaults to a task called `"Administration"` when
   present.
4. A month prompt (default: current month, `YYYY-MM`).
5. A preview table, one row per Mon–Fri of the chosen month. Rows where
   you have no existing time entries default to 8.00h; rows where you
   already logged some time (across any project/task) default to
   `8 − existing_total` so the day tops up to 8h; rows where you already
   logged ≥ 8h appear as `[already logged]` and are locked (FR-012). Use
   ↑/↓ to move; the focused row is highlighted.
6. On any row, press Enter to open a sub-menu:
   - **Plain row** (empty day): Skip / Change hours / Back.
   - **Top-up row** (partial day): Skip / Change hours / Back (same as plain;
     only the default hours differ).
   - **Skipped row**: Include / Change hours / Back.
   - **Already-logged row**: Back only (locked — can't re-include).
7. When the preview looks right, scroll to **`✅ Approve & submit`** and
   press Enter.
8. The CLI sends a single bulk request. You'll see:

   ```
   Created 22 entries in Moco for 2026-06.
   ```

To cancel without writing anything to Moco, scroll to
**`❌ Cancel`** and press Enter, or hit Ctrl-C at any prompt.

---

## 4. Fill a different month

```bash
moco-filler --month 2026-07
```

`--month` is the only flag in v1. Format is strict `YYYY-MM`; anything else
exits `1` with a usage error.

---

## 5. Verify (per User Story 1's Independent Test)

After an approved run:

1. Open `https://statista.mocoapp.com/activities` in your browser.
2. Filter to the chosen month, project, task.
3. Confirm one 8-hour entry exists for every Mon–Fri.
4. Confirm there are **no** entries on Saturday or Sunday (SC-002).
5. From the repo root:

   ```bash
   grep -r "<first 8 chars of your key>" . --include="*"
   ```

   This should print nothing (SC-004).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Authentication failed: check your Moco API key.` (exit 2) | Key wrong or revoked | Regenerate the personal API key in Moco. |
| `No projects are assigned to your Moco account.` (exit 3) | API key works but your account has no project assignments | Ask a Moco admin to assign you to a project. |
| `Selected project has no tasks.` (exit 4) | Chosen project has no tasks in Moco | Pick a different project, or have one added in Moco. |
| `No entries to submit; exiting.` (exit 5) | You skipped every row in the preview | Re-run and include at least one row before approving. |
| `Bulk submission failed; no entries were created.` (exit 6) | Network failure or Moco-side error; no rows were created | Re-run; the tool is safe to retry because no entries were created on failure. |
| `Created M of N entries for <YYYY-MM>. Failed: …` (exit 7) | Moco accepted some rows and rejected others | Re-run; the "already logged" rule (FR-012) will exclude the dates that did succeed, so the second run retries only the still-missing dates. |
