# Feature Specification: Moco Monthly Time Tracker CLI

**Feature Branch**: `001-create-mvp-moco-filler-app`

**Created**: 2026-06-01

**Status**: Accepted

**Input**: User description: "Build a Python CLI that fills time entries in the Moco time-tracking app (https://statista.mocoapp.com/activities) for every weekday of a chosen month at 8 hours/day. The CLI must let the user provide an API key at startup (not stored on disk), pull the list of projects and a chosen project's tasks (specifically the 'Administration' task), preview the planned entries in a pretty, navigable, editable table, then submit the entire month in a single bulk operation only after the user approves the preview visually."

## Clarifications

### Session 2026-06-01

- Q: How should the spec model the outcome of bulk submission when some rows succeed and others fail? → A: Per-row outcomes — report which dates succeeded and which failed, and let the user re-run to retry just the failed dates.
- Q: What should happen when an included row has its hours set to 0? → A: Auto-skip at zero — hours = 0 implicitly excludes the row from the bulk submission; no 0-hour entries are ever sent to Moco.
- Q: What is the maximum hours value a row may hold? → A: 8 hours per day — values > 8 are rejected at input.
- Q: How should "already logged" be defined for FR-012, and what should the planned hours be on a partially-filled day? → A: Sum the user's existing entries on the date across all projects/tasks; if the total is ≥ 8h the date is excluded as "already logged" (day full); if the total is > 0 but < 8h the row stays included with planned hours auto-set to `8 − existing_total` (top-up to 8h).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fill a full month of weekdays at 8 hours and approve before submitting (Priority: P1)

A user opens a terminal at the start (or end) of a month to record their time in Moco. They launch the CLI, provide their personal Moco API key in a one-time prompt that is never written to disk, pick their target project, pick the "Administration" task within that project, and ask the tool to plan 8 hours of time entries on every weekday of the chosen month. The CLI shows them a pretty preview table with one row per weekday. The user moves up and down through the rows with arrow keys; the row they are on is visually highlighted. They confirm the plan looks right and approve it. The CLI submits all entries to Moco in a single bulk request and reports success.

**Why this priority**: This is the entire purpose of the tool. Without it, the user gains nothing over the existing browser workflow. The end-to-end flow (auth → select project/task → preview → approve → bulk submit) is the MVP.

**Independent Test**: A user supplies a valid Moco API key for a sandbox account, runs the CLI for a chosen month (e.g., June 2026), navigates through the preview, approves it, and afterwards verifies via the Moco web UI that an 8-hour Administration entry exists for every weekday in that month and none on the weekends.

**Acceptance Scenarios**:

1. **Given** the user has a valid Moco API key and at least one project containing an "Administration" task, **When** they launch the CLI and complete the project/task selection and month entry, **Then** the CLI displays a preview table containing exactly one row per Mon–Fri date in the chosen month, each showing 8 hours (or fewer per FR-012 on days where the user already has partial existing entries).
2. **Given** the preview table is displayed, **When** the user presses the up/down arrow keys (or equivalent navigation), **Then** the currently focused row is visually highlighted and the highlight follows the user's navigation.
3. **Given** the user is viewing the preview and presses the explicit "approve" action, **Then** the CLI submits all rows in a single bulk request and displays a success confirmation listing the number of entries created.
4. **Given** the user is viewing the preview, **When** they press "cancel" or quit, **Then** no request is sent to Moco and the program exits cleanly with a message confirming nothing was submitted.
5. **Given** the chosen month contains a weekend, **When** the preview is generated, **Then** Saturday and Sunday dates are not present in the table and not part of any submission.

---

### User Story 2 - Provide API credentials safely for the session only (Priority: P1)

The user must be able to authenticate with Moco without ever creating a config file in the repository that could be accidentally committed. They expect to type or paste their API key at startup, have it kept only for the duration of the run, and have it accepted via an environment variable as an alternative for power users.

**Why this priority**: Without safe credential handling the tool is unusable in practice — the user explicitly does not want a checked-in key. This is a precondition of every other scenario.

**Independent Test**: Run the CLI in a freshly cloned working directory, supply the key interactively, complete a run, then verify that no file inside the project directory contains the key and no key remains in shell history when entered through the interactive prompt.

**Acceptance Scenarios**:

1. **Given** no environment variable is set, **When** the CLI starts, **Then** it prompts for the API key with a masked input (no echo).
2. **Given** the user supplies a valid key interactively, **When** the CLI finishes (success, cancel, or crash), **Then** no project file contains the key and no new file is created inside the repository to hold it.
3. **Given** the user supplies an invalid or revoked key, **When** the first API call fails authentication, **Then** the CLI shows a clear error message identifying authentication as the problem and exits without proceeding to selection or preview.

---

### User Story 3 - Edit the preview before approving (Priority: P2)

While viewing the preview, the user wants to make last-minute adjustments — for example, drop a vacation day, change a half-day to 4 hours, or skip a public holiday — without leaving the CLI or restarting it.

**Why this priority**: The user explicitly asked for an editable preview. It is critical for accuracy but the P1 flow can still deliver value with a default 8-hour-everywhere plan if editing is temporarily limited.

**Independent Test**: Open the preview, navigate to a row, change its hours and/or mark it as skipped, then approve and confirm the submitted entries reflect the edits exactly (a skipped day produces no entry; an edited day produces an entry with the new hours).

**Acceptance Scenarios**:

1. **Given** a row is focused in the preview, **When** the user invokes the edit action and enters a new hours value, **Then** the row redraws with the new value and the running monthly total updates.
2. **Given** a row is focused, **When** the user marks the row as skipped, **Then** the row is visually marked as excluded and is not included in the bulk submission.
3. **Given** the user has made edits and approves, **When** the CLI submits, **Then** the submitted payload matches what the table showed at the moment of approval (no silent reset to defaults).

---

### Edge Cases

- The chosen month has no rows left to submit (every row skipped during editing): the CLI must refuse to submit and tell the user there is nothing to do.
- The API returns no projects, or the chosen project has no tasks named "Administration": the CLI must surface a clear, actionable error and not silently fall back to another task.
- The bulk submit succeeds for some entries and fails for others (partial failure): the CLI must report which dates failed and which succeeded; the user should be able to retry just the failed ones in a future run.
- The user enters a month entirely in the future or entirely in the past: behave the same as the current month — Moco itself is the source of truth for whether the entry is allowed.
- The user's terminal is narrower than the table needs: the table must still render readably (truncate columns or wrap, but never corrupt navigation).
- The user runs the CLI for a month where some weekdays already have time entries: weekdays whose existing entries (across all projects and tasks) total ≥ 8 hours appear in the preview marked "already logged", are excluded from the submission, and cannot be re-included from inside the CLI (per FR-012). Weekdays whose existing entries total > 0 but < 8 hours appear with their planned hours auto-reduced to `8 − existing_total` so the resulting submission tops the day up to 8 hours.
- Network failure during the bulk request: the CLI must not leave the user guessing — it reports the failure and tells the user the entries were not created.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The CLI MUST prompt the user for a Moco API key at startup using a masked input field, OR accept the key from an environment variable, and MUST NOT persist the key to any file in the project directory or any other on-disk location.
- **FR-002**: The CLI MUST allow the user to specify a target month (e.g., `2026-06`) and default to the current month if the user supplies no value.
- **FR-003**: The CLI MUST retrieve the list of projects available to the authenticated user and let the user choose one interactively.
- **FR-004**: The CLI MUST retrieve the tasks of the chosen project and let the user select the task to bill against (defaulting to a task named "Administration" if one exists, with the option to pick a different task).
- **FR-005**: The CLI MUST compute the set of Mon–Fri dates in the chosen month and generate one planned entry per date, defaulting to 8 hours and excluding Saturdays and Sundays. The default may be reduced for partially-filled days per FR-012.
- **FR-006**: The CLI MUST display the planned entries as a formatted table with one row per date, showing at minimum the date, weekday, hours, project name, and task name.
- **FR-007**: The CLI MUST visually highlight the currently focused row as the user navigates up and down through the table.
- **FR-008**: The user MUST be able to edit the preview before submission. Per row, the user can (a) change the hours value from the default 8 to any value in the closed range `[0, 8]` and (b) toggle the row between "included" and "skipped". Values outside `[0, 8]` MUST be rejected at input. Setting a row's hours to 0 MUST implicitly mark it as skipped and exclude it from the submission — the CLI MUST NOT send a 0-hour entry to Moco. Per-row description text is NOT editable in v1 — all entries share a single fixed description (see Assumptions).
- **FR-009**: The CLI MUST require an explicit user approval action before any data is sent to Moco. Closing or quitting the preview without that approval MUST result in no submission.
- **FR-010**: The CLI MUST submit all approved entries in a single bulk request to the Moco activities endpoint.
- **FR-011**: The CLI MUST report the outcome of submission on a per-row basis. On full success it confirms every planned row was created. If some rows succeed and others fail, it MUST list which dates succeeded and which failed (with the per-date failure reason where the API provides one) and inform the user that re-running the CLI for the same month will retry only the still-missing dates (via the "already logged" exclusion in FR-012).
- **FR-012**: For each weekday in the chosen month the CLI MUST compute the user's existing-hours total on that date by summing every time entry the user already has on that date across all projects and tasks (not only the chosen project/task). Then:
  - If the existing-hours total is ≥ 8, the row MUST be marked "already logged" (day full), excluded from the submission batch, and the user MUST be prevented from toggling it back to "included" — pushing the day past 8 hours must be done in the Moco web UI.
  - If the existing-hours total is > 0 but < 8, the row MUST remain "included" with its planned hours auto-set to `8 − existing_total` so submission tops the day up to exactly 8 hours. The user MAY still edit the row's hours (within `[0, 8]`) or skip it before approving.
  - If the existing-hours total is 0, the row uses the default 8-hour plan from FR-005.
- **FR-013**: The CLI MUST surface authentication errors, missing-project errors, and missing-task errors as plain-language messages and exit with a non-zero status without sending any further requests.
- **FR-014**: The CLI MUST NOT include weekend dates in the preview or in any submission, regardless of user edits.

### Key Entities

- **API Key**: The user's personal Moco API token. Held only in memory for the duration of one run. Never persisted by this tool. Used to authenticate every request to Moco.
- **Project**: A unit of work in Moco, identified by an ID and a name. Has a list of tasks. The user picks one project per run.
- **Task**: A category of activity within a project (the user wants the "Administration" task by default). Identified by an ID and a name within its project.
- **Planned Entry**: A row in the preview table representing one prospective time entry. Has a date, weekday, hours (default 8), project reference, task reference, optional description, and a skipped/included flag.
- **Submission Batch**: The collection of all non-skipped Planned Entries that the user approves. Sent to Moco as one bulk request.
- **Submission Result**: The per-row outcome of the bulk request — for each submitted Planned Entry, whether it was created or failed (and, where the API provides one, the failure reason). Used by FR-011 to drive the user-facing report and by FR-012's "already logged" exclusion to make re-runs retry only the still-missing dates.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can complete the full happy path (launch → authenticate → choose project → choose task → choose month → preview → approve → success message) in under 2 minutes for a typical month, assuming a responsive network.
- **SC-002**: 100% of weekend dates in the chosen month are absent from both the preview and the submission, with zero exceptions across any month tested.
- **SC-003**: After an approved run, the count of new time entries visible in Moco for the chosen month equals the number of non-skipped rows shown in the preview at the moment of approval. No silent additions, no silent omissions.
- **SC-004**: Zero project files contain the API key at any point, verifiable by a text search across the repository after any run (successful, cancelled, or crashed).
- **SC-005**: The user can navigate the preview and reach any row in the table using only the keyboard, with the highlighted row always visible on screen.
- **SC-006**: A user who quits the preview without approving sees, in Moco, exactly zero new entries created by this tool.

## Assumptions

- The user has a valid Moco account at `https://statista.mocoapp.com` and a personal API key that grants permission to read projects and create activities on behalf of the user themselves.
- The Moco instance, projects, tasks, and bulk-activity submission behavior used by the user are stable and accessible from the user's machine over the network at run time.
- "Administration" refers to a task name inside the chosen project, not a separate Moco concept. If a project does not contain such a task, the user can still pick a different task at the selection step.
- "8 hours per weekday" is the default plan for the current need; users may edit each row's hours within `[0, 8]` in the preview per FR-008.
- Public/national holidays are NOT auto-excluded in v1. Users who want to skip holidays do so via the preview's edit/skip flow.
- In v1 every submitted entry uses the same fixed description (a sensible constant such as "Administration") chosen at run time or hard-coded; per-row description editing is out of scope.
- The CLI is intended to be run interactively in a terminal that supports keyboard navigation and basic ANSI styling; headless/scripted use is out of scope for v1.
- Only one project + one task per run is supported in v1. Mixed-project months are out of scope for v1.
- The user is the only target audience for v1; multi-user features (impersonation, team-wide submission) are out of scope.
