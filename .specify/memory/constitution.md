<!--
SYNC IMPACT REPORT - Version 1.1.0
==================================
- Version change: 1.0.0 → 1.1.0 (MINOR — materially expanded Commit Discipline guidance)
- Modified principles:
  - II. Atomic Commits — added cross-reference to mandatory commit-message "why" rule
- Added sections: none (rule placed inside existing Development Workflow → Commit Discipline)
- Removed sections: none
- New requirements:
  - Commit messages MUST include a brief explanation of *why* the change was made,
    not only *what* changed.
- Templates requiring updates:
  - ✅ .specify/memory/constitution.md (this file)
  - ⚠ pending .specify/extensions/git/git-config.yml — auto-commit `message` values are
    currently static "what" strings (e.g., "[Spec Kit] Add specification"); they do not
    encode a per-change "why". Either (a) replace them with templates the invoking command
    fills in with a reason, or (b) require manual commits for changes that need a specific
    "why". Flagged for follow-up; not amended here because the right path depends on
    extension behavior the user has not yet decided.
  - ✅ .specify/templates/plan-template.md — no commit-message guidance to update
  - ✅ .specify/templates/spec-template.md — no commit-message guidance to update
  - ✅ .specify/templates/tasks-template.md — generic "Commit after each task" line is
    consistent with the new rule; no change required
- Follow-up TODOs:
  - TODO(GIT_EXTENSION_MESSAGES): decide whether speckit.git.commit messages should be
    parameterized to carry a "why", or whether automated commits are exempt from the rule.
-->

# CLI Apps Constitution

## Core Principles

### I. Python3 & Questionary-First

All CLI applications in this project MUST be implemented in Python3 with Questionary for interactive user interfaces. Interactive prompts MUST use Questionary's question types (Text, Confirm, Select, etc.) for consistent UX. Libraries must be self-contained, independently usable, and not require external service dependencies beyond their core functionality.

### II. Atomic Commits (NON-NEGOTIABLE)

Every commit MUST represent exactly one complete, logical step. A commit must be:
- Buildable and testable in isolation (no broken intermediate states)
- Self-contained with no dangling dependencies across commits
- Reviewable in 5 minutes or less without context beyond the commit message
- Reversible without cascading failures
- Accompanied by a commit message that states *why* the change was made (see
  Commit Discipline below); the "why" is part of what makes a commit reviewable
  in isolation and is therefore non-negotiable

Large features are broken into smaller, atomic commits. No "work in progress" or partial implementations are committed to any branch.

### III. Clean Code & Readability

Code MUST follow PEP 8 style guide and SOLID principles. Each function/class has a single, clear purpose expressed in its name. Names are explicit and self-documenting. Logic is straightforward—complex branching or nested structures indicate need for refactoring. Type hints are encouraged for clarity. Docstrings are minimal: only explain the WHY if non-obvious; never repeat what the code already shows.

### IV. Unit Tests Only (NON-NEGOTIABLE)

Unit tests are mandatory for all business logic. Integration tests are explicitly NOT required for MVP. Test files MUST be co-located with or directly adjacent to source code. Test names MUST describe the scenario being tested (e.g., `test_parse_valid_input`, not `test_1`). Tests are written before or alongside implementation; no untested code is merged.

### V. Single Responsibility & Modularity

Each module, class, and function has exactly one reason to change. A CLI module handles argument parsing and user interaction; business logic lives in separate, testable modules. UI concerns (Questionary prompts) are isolated from data processing logic. Circular imports are eliminated through careful dependency structure.

## Technology Stack & Dependencies

**Language**: Python 3.9+

**CLI Framework**: Questionary for interactive prompts

**Testing**: pytest for unit tests

**Code Quality**:
- PEP 8 compliance (checked via linting if applicable)
- Type hints recommended for public APIs
- No external service dependencies in core libraries

**Dependency Management**: Minimize external dependencies; prefer standard library when feasible. All dependencies MUST be documented in a requirements file with pinned versions for reproducibility.

## Development Workflow

### Commit Discipline

- **Before commit**: Run unit tests locally; ensure all tests pass
- **Commit message format**: Concise, imperative subject line (e.g., "Add user
  input validation" not "Added validation")
- **Commit messages MUST explain *why* (NON-NEGOTIABLE)**: Every commit message
  MUST include a brief statement of the motivation for the change — the problem
  being solved, the constraint being satisfied, or the decision being recorded —
  not only a description of what changed. The "why" MAY appear:
  - On the subject line when it fits naturally and stays under ~72 characters
    (e.g., `Pin requests<3 to avoid TLS regression in 3.0`), OR
  - In a body paragraph separated from the subject by a blank line, when the
    reason needs more than a few words
  Acceptable forms of "why" include: the user-visible problem, the bug or
  incident reference, the prior decision being reversed, or the constraint
  (security, compliance, performance) being honored. "Refactor", "cleanup", or
  "update" with no further explanation is NOT acceptable.
- **One commit = one logical change**: If you describe it with "and" or "also",
  split into multiple commits
- **No merge commits on feature branches**: Use rebase for linear history

### Code Review Expectations

- All code MUST pass unit tests before review
- Reviewers verify: single responsibility principle, atomic nature of change, clean code readiness, and that the commit message explains *why* the change was made
- Complex commits are rejected with request to split into smaller steps
- Commits whose messages do not explain *why* MUST be amended (or replaced via interactive rebase before merge) before the change is accepted
- Constitution compliance (especially atomic commit, commit-message "why", and test coverage) is non-negotiable

## Governance

This Constitution supersedes all other development practices. Amendments require:
1. Explicit documentation of the change
2. Ratification consensus among project maintainers
3. Migration plan for existing code (if backward-incompatible)

All commits MUST comply with non-negotiable principles (Atomic Commits, including the commit-message "why" requirement, and Unit Tests Only). Violations MUST be resolved before merge.

**Constitution Check** performed during code review gates compliance with this constitution. Type hints and clean code are validated through pragmatic review, not automated gates.

**Version**: 1.1.0 | **Ratified**: 2026-06-01 | **Last Amended**: 2026-06-01
