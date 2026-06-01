# cli-apps

This repository hosts small CLI tools. The first one is **moco-filler** —
a Python CLI that fills a chosen month of Moco weekday time entries at 8
hours/day. See [`specs/001-moco-time-tracker/quickstart.md`](specs/001-moco-time-tracker/quickstart.md)
for the install + run walkthrough.

## Quick install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Run

```bash
export MOCO_API_KEY="<your Moco personal API key>"
moco-filler --month 2026-06
```

See the [quickstart](specs/001-moco-time-tracker/quickstart.md) for the
interactive flow, exit codes, and troubleshooting.

## Tests

```bash
pytest
```

## Specs

Per [Constitution](.specify/memory/constitution.md) the project follows a
Spec-Kit driven workflow: see `specs/<feature>/` for `spec.md`, `plan.md`,
`tasks.md`, and the supporting design artifacts behind each feature.
