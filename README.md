# cli-apps

A growing collection of small, focused Python CLI tools. The repository
is intentionally generic — every tool lives in its own package under
`src/`, ships its own README, and is delivered through the same
spec-driven workflow described below. New tools are added by repeating
the workflow, not by reshaping the repo.

## Available tools

| Tool | What it does | Docs |
|------|--------------|------|
| **moco-filler** | Fills a chosen month of Moco weekday time entries (8h/day, top-ups, Hamburg holiday auto-skip). | [`src/moco_filler/README.md`](src/moco_filler/README.md) |
| _more soon_ | Additional CLI tools land here as new packages under `src/`. | — |

## Spec-Driven Development with GitHub Spec Kit

Every tool in this repo is built with **[GitHub Spec Kit][spec-kit]** —
a workflow where you write the specification first, get it agreed, then
let an AI agent execute the spec. The process flows through a small set
of slash-commands (`/speckit-specify` → `/speckit-clarify` →
`/speckit-plan` → `/speckit-tasks` → `/speckit-implement`) and produces
a trail of immutable design artifacts (`spec.md`, `plan.md`,
`research.md`, `data-model.md`, `contracts/`, `tasks.md`) for each
feature under `specs/`.

> **Source — read this for the approach:**
> [Spec-Driven Development with Spec Kit][source] by Hashaam Khan
> (Medium).

<p align="center">
  <a href="https://medium.com/@hashaamkhan975/spec-driven-development-with-spec-kit-34c443e3eaf6">
    <img src="https://miro.medium.com/v2/resize:fit:1400/format:webp/1*swVvm0WtYzMl2vVSgKSV9w.jpeg" alt="Spec-Driven Development with Spec Kit" width="600">
  </a>
</p>

<p align="center"><sub>Image source: <a href="https://medium.com/@hashaamkhan975/spec-driven-development-with-spec-kit-34c443e3eaf6">Spec-Driven Development with Spec Kit</a> — Hashaam Khan, Medium.</sub></p>

### Why spec-first?

- The agent commits no code until the spec, the plan, and the task list
  are accepted — so course-correction happens on prose, not on diffs.
- Every feature lands with a checklist of measurable success criteria
  (e.g., `SC-001 … under 1 second`, `SC-005 … zero ANSI escapes`), so
  "done" has a single definition.
- The artifact trail means future contributors (human or AI) can
  re-derive *why* a decision was made by reading
  [`specs/<feature>/`](specs/) instead of `git blame`-ing forever.

[spec-kit]: https://github.com/github/spec-kit
[source]: https://medium.com/@hashaamkhan975/spec-driven-development-with-spec-kit-34c443e3eaf6

## Model & roadmap

| Today | Roadmap |
|-------|---------|
| The agent that builds the tools is a **single model** (Claude). | Move to a **multi-model** setup — the right model for the job (architecture, refactor, review, lint) rather than one generalist for everything. The Spec Kit artifacts already make this swap cheap: every phase's input/output is plain text, so a different model can pick up at any of `specify` / `clarify` / `plan` / `tasks` / `implement` without re-reading the entire history. |

## Repository layout

```text
.
├── src/
│   └── moco_filler/          # First CLI tool — see its README
│       └── README.md         # Tool-specific usage docs
├── tests/                    # One test file per source module
├── specs/                    # Per-feature spec / plan / tasks / contracts
│   └── <NNN-feature-name>/
│       ├── spec.md           # WHAT and WHY (no implementation details)
│       ├── plan.md           # Technical context + constitution gates
│       ├── research.md       # Decisions for each unknown
│       ├── data-model.md     # Entities + relationships
│       ├── contracts/        # External / internal interface contracts
│       ├── quickstart.md     # Developer-facing how-to
│       └── tasks.md          # Per-task breakdown the agent executes
├── .specify/
│   ├── memory/constitution.md   # Non-negotiable project rules
│   ├── templates/               # Spec / plan / tasks templates
│   ├── scripts/                 # Helper scripts (setup, prerequisites)
│   ├── extensions/git/          # Git extension hooks (commit + branch)
│   └── feature.json             # Current active feature pointer
├── CLAUDE.md                 # Context loaded by Claude Code each session
├── pyproject.toml            # Currently scoped to moco-filler
└── README.md                 # This file
```

## Install

```bash
git clone <repo-url> cli-apps
cd cli-apps
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

`pip install -e .` currently exposes the `moco-filler` console script
because `pyproject.toml` is scoped to that one package. When the second
tool lands, that file becomes per-package and the install step grows
accordingly.

## Tests

```bash
pytest
```

## Add a new CLI tool

1. Run `/speckit-specify "<one-line description>"` in Claude Code (or
   write `specs/<NNN-name>/spec.md` by hand following the template at
   `.specify/templates/spec-template.md`).
2. Optionally clarify with `/speckit-clarify` — resolves the
   highest-impact ambiguities into the spec.
3. `/speckit-plan` → emits `plan.md`, `research.md`, `data-model.md`,
   `contracts/`, `quickstart.md`.
4. `/speckit-tasks` → emits `tasks.md` (per-user-story atomic tasks).
5. `/speckit-implement` → executes the tasks, leaving green tests at
   each phase.
6. Add the new tool's row to the table at the top of this file.

The [Constitution](.specify/memory/constitution.md) is the
non-negotiable layer underneath all of the above — atomic commits,
unit tests only, single responsibility per module, Python + Questionary
for interactive prompts.

## License

Proprietary — see individual tool packages for their license terms.
