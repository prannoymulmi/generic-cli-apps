# cli-apps

This repository hosts small CLI tools. The first one is **moco-filler** —
a Python CLI that fills a chosen month of Moco weekday time entries at 8
hours/day. See [`specs/001-moco-time-tracker/quickstart.md`](specs/001-moco-time-tracker/quickstart.md)
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
4. On any row: `Skip` / `Include` / `Change hours` (0–8) / `Back`.
5. `✅ Approve & submit` → one `POST /activities/bulk` request.
6. `❌ Cancel` (or Ctrl-C) → exits without contacting Moco.

## Tests

```bash
pytest
```

## Specs

Per [Constitution](.specify/memory/constitution.md) the project follows a
Spec-Kit driven workflow: see `specs/<feature>/` for `spec.md`, `plan.md`,
`tasks.md`, and the supporting design artifacts behind each feature.
