"""``moco-filler`` CLI entrypoint — orchestration only.

The thin glue between Questionary, the Moco HTTP client, the planner,
and the preview. Each step is a small dispatch into another module per
Constitution §V, so this file should read top-to-bottom as the
"interactive flow" laid out in
``specs/001-create-mvp-moco-filler-app/contracts/cli.md``.

US1 reads the API key from ``MOCO_API_KEY`` only; US2 (T024) replaces
that with the env-or-masked-prompt fallback.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

import questionary

from moco_filler.auth import resolve_credentials
from moco_filler.calendar_utils import parse_month, weekday_dates
from moco_filler.errors import (
    BulkPartialFailureError,
    BulkTotalFailureError,
    MocoFillerError,
    NoTasksError,
    NothingToSubmitError,
)
from moco_filler.holidays import get_hamburg_holidays
from moco_filler.moco_client import MocoClient
from moco_filler.models import (
    Project,
    SubmissionBatch,
    SubmissionResult,
    Task,
)
from moco_filler.planner import build_planned_entries
from moco_filler.preview import show_preview
from moco_filler.styling import select_kwargs


MOCO_BASE_URL = "https://statista.mocoapp.com/api/v1"
DEFAULT_DESCRIPTION = "Administration"

EXIT_BAD_INPUT = 1
EXIT_OK = 0


class _Parser(argparse.ArgumentParser):
    """argparse subclass that exits ``1`` on parse errors per cli.md."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_BAD_INPUT)


def main(argv: Optional[List[str]] = None) -> int:
    parser = _Parser(
        prog="moco-filler",
        description=(
            "Fill weekday Moco time entries at 8h/day for a chosen month."
        ),
    )
    parser.add_argument(
        "--month",
        type=str,
        default=None,
        help="Target month in YYYY-MM (defaults to the current month).",
    )
    args = parser.parse_args(argv)

    try:
        return _run(args)
    except MocoFillerError as exc:
        message = str(exc)
        if message:
            print(message, file=sys.stderr)
        return exc.exit_code


def _run(args: argparse.Namespace) -> int:
    try:
        year, month = parse_month(args.month)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_BAD_INPUT

    credentials = resolve_credentials()
    client = MocoClient(
        token=credentials.token, base_url=MOCO_BASE_URL
    )
    user_id = client.get_session()
    projects = client.get_projects_assigned()

    project = _pick_project(projects)
    if project is None:
        return _cancelled()

    task = _pick_task(project)
    if task is None:
        return _cancelled()

    weekdays = weekday_dates(year, month)
    holiday_catalogue = get_hamburg_holidays(year)
    activities = client.get_activities(
        from_date=weekdays[0],
        to_date=weekdays[-1],
        user_id=user_id,
    )
    entries = build_planned_entries(
        year, month, activities, holiday_catalogue
    )

    decision = show_preview(entries)
    if decision == "cancel":
        return _cancelled()

    submitable = [e for e in entries if e.is_submitable]
    if not submitable:
        print("No entries to submit; exiting.")
        raise NothingToSubmitError()

    batch = SubmissionBatch(
        project_id=project.id,
        task_id=task.id,
        description=DEFAULT_DESCRIPTION,
        billable=False,
        entries=submitable,
    )
    result = client.bulk_create(batch)
    return _render_result(result, f"{year:04d}-{month:02d}")


def _pick_project(projects: List[Project]) -> Optional[Project]:
    sorted_projects = sorted(projects, key=lambda p: p.name.lower())
    return questionary.select(
        "Which project would you like to book against?",
        choices=[
            questionary.Choice(title=p.name, value=p)
            for p in sorted_projects
        ],
        **select_kwargs(),
    ).ask()


def _pick_task(project: Project) -> Optional[Task]:
    if not project.tasks:
        raise NoTasksError(
            f"Project {project.name!r} has no tasks."
        )
    default_task = next(
        (t for t in project.tasks if t.name == "Administration"),
        None,
    )
    return questionary.select(
        "Which task would you like to book?",
        choices=[
            questionary.Choice(title=t.name, value=t)
            for t in project.tasks
        ],
        default=default_task.name if default_task else None,
        **select_kwargs(),
    ).ask()


def _render_result(result: SubmissionResult, month_label: str) -> int:
    n = len(result.entries)

    if result.succeeded:
        print(f"Created {n} entries in Moco for {month_label}.")
        return EXIT_OK

    if not result.any_created:
        print("Bulk submission failed; no entries were created.")
        reason = next(
            (
                e.error_message
                for e in result.entries
                if e.error_message
            ),
            None,
        )
        raise BulkTotalFailureError(reason or "")

    failed_pairs = ", ".join(
        f"{e.date.isoformat()} ({e.error_message or 'unknown error'})"
        for e in result.entries
        if e.status == "failed"
    )
    print(
        f"Created {result.created_count} of {n} entries for "
        f"{month_label}. Failed: {failed_pairs}"
    )
    raise BulkPartialFailureError(
        f"{result.failed_count} of {n} entries failed"
    )


def _cancelled() -> int:
    print("Nothing was submitted.")
    return EXIT_OK
