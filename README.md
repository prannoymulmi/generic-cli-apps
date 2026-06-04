# cli-apps

This repository hosts small CLI tools. The first one is **moco-filler** —
a Python CLI that fills a chosen month of Moco weekday time entries at 8
hours/day. See [`specs/001-create-mvp-moco-filler-app/quickstart.md`](specs/001-create-mvp-moco-filler-app/quickstart.md)
for the full walkthrough, troubleshooting table, and SC-004 verification.

## 1. Install

```bash
git clone <repo-url> cli-apps
cd cli-apps
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

`pip install -e .` exposes the `moco-filler` console script.

## 2. Get your Moco API key

1. Sign in to `https://statista.mocoapp.com`.
2. Open your user profile → Personal API Key, copy it.
3. Either paste it into the masked prompt at launch, or export it once
   per shell:

   ```bash
   export MOCO_API_KEY="paste-your-key-here"
   ```

   The CLI **never** writes this value to disk (FR-001, SC-004).

## 3. Fill a month

```bash
moco-filler              # current month
moco-filler --month 2026-07
```

The interactive flow (per `contracts/cli.md`):

1. Masked API-key prompt (skipped when `MOCO_API_KEY` is set).
2. Project picker → task picker (defaults to `Administration`).
3. Preview — one row per Mon–Fri of the chosen month. Existing entries
   (across **all** projects/tasks) top each day up to 8h; days already
   at ≥ 8h appear as `[already logged]` and are locked (FR-012).
   Hamburg public holidays are auto-skipped and labelled
   `[holiday: <name>]` in the preview (features 003 / 004).
4. On any row: `Skip` / `Include` / `Change hours` (0–8) / `Back`.
   `Include` on a holiday row overrides the auto-skip; `Skip` again
   restores it.
5. `✅ Approve & submit` → one `POST /activities/bulk` request.
6. `❌ Cancel` (or Ctrl-C) → exits without contacting Moco.

## Hamburg holiday cache

The first run that needs a calendar year fetches its Hamburg holidays
from `date.nager.at` and writes them to a per-user cache:

| Platform | Path |
|----------|------|
| macOS | `~/Library/Caches/moco-filler/holidays.json` |
| Linux | `${XDG_CACHE_HOME:-$HOME/.cache}/moco-filler/holidays.json` |
| Windows | `%LOCALAPPDATA%\moco-filler\Cache\holidays.json` |

Subsequent runs read from the cache — no further network calls for
holiday data. **To force a refresh**, delete the file (or the inner
year entry); the next run repopulates it. If the source is unreachable
on a cold cache, the CLI degrades silently (no holiday rows marked,
no crash); next online run repopulates. See
[`specs/004-cache-holidays-locally/quickstart.md`](specs/004-cache-holidays-locally/quickstart.md)
for the full reference.

## Tests

```bash
pytest
```

## Specs

Per [Constitution](.specify/memory/constitution.md) the project follows a
Spec-Kit driven workflow: see `specs/<feature>/` for `spec.md`, `plan.md`,
`tasks.md`, and the supporting design artifacts behind each feature.
