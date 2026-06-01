<!-- 
SYNC IMPACT REPORT - Version 1.0.0
==================================
- Version change: [template] → 1.0.0 (initial ratification)
- Core Principles defined: 5
- Technology Stack section added
- Development Workflow section added
- New principles: Python3-First, Atomic Commits, Clean Code, Unit Tests Only, Single Responsibility
- All template placeholders resolved
- No placeholder deferments necessary
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
- **Commit message format**: Concise, imperative (e.g., "Add user input validation" not "Added validation")
- **One commit = one logical change**: If you describe it with "and" or "also", split into multiple commits
- **No merge commits on feature branches**: Use rebase for linear history

### Code Review Expectations

- All code MUST pass unit tests before review
- Reviewers verify: single responsibility principle, atomic nature of change, clean code readiness
- Complex commits are rejected with request to split into smaller steps
- Constitution compliance (especially atomic commit and test coverage) is non-negotiable

## Governance

This Constitution supersedes all other development practices. Amendments require:
1. Explicit documentation of the change
2. Ratification consensus among project maintainers
3. Migration plan for existing code (if backward-incompatible)

All commits MUST comply with non-negotiable principles (Atomic Commits, Unit Tests Only). Violations MUST be resolved before merge.

**Constitution Check** performed during code review gates compliance with this constitution. Type hints and clean code are validated through pragmatic review, not automated gates.

**Version**: 1.0.0 | **Ratified**: 2026-06-01 | **Last Amended**: 2026-06-01
