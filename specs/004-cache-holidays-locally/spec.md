# Feature Specification: Cache Hamburg Holidays Locally After One Download

**Feature Branch**: `004-cache-holidays-locally`

**Created**: 2026-06-04

**Status**: Draft

**Input**: User description: "just download the holidays for the year once save it locally so local holidays are not always quried"

## Context

Feature 003 (`specs/003-hamburg-holidays-skip`) introduced Hamburg
public-holiday awareness in the preview. Its v1 spec assumed the
holiday catalogue would ship inside the tool — computed for movable
feasts, hard-coded for fixed ones — with **no network call**.

The user has now revised that direction: the tool should **download
the holidays for a year once** from an authoritative source, **persist
them to a local cache**, and use the cache on every subsequent run.
That way the source of truth is up-to-date data instead of a
hand-maintained table inside the tool, but the cost is paid only on
the first run for a given year — not on every CLI invocation.

This feature **amends** the bundled-catalogue assumption from feature
003. The user-visible behaviour from feature 003 (auto-skip, named
holiday row, override, fallback when no holiday data is available) is
unchanged; only the source of the holiday list moves from
"compiled-in" to "fetched once, cached locally".

## User Scenarios & Testing *(mandatory)*

A user runs `moco-filler` for a chosen month. The CLI needs the Hamburg
public-holiday list for that month's year. Today (under feature 003)
the list is baked into the code; under this feature, the list is
downloaded once per year and cached on the user's machine. A user who
runs the CLI ten times for May 2026 should see exactly one network
fetch — on the first run — and zero on every subsequent run.

### User Story 1 — Fetch holidays once, then reuse from the local cache (Priority: P1) 🎯 MVP

The first time the CLI needs Hamburg public holidays for a calendar
year, it fetches the list from an authoritative source and writes
the result to a local cache file on the user's machine. Every
subsequent run that needs the same year reads from the cache without
contacting the network at all.

**Why this priority**: This is the entire feature — eliminate
repeated network calls. Without it, every CLI run pays a network
round-trip for data that almost never changes within a year.

**Independent Test**: With no cache present, run `moco-filler --month
2026-05`. Confirm exactly one network call to the holiday source is
made and a cache file is created. Then run `moco-filler --month
2026-05` again (or `--month 2026-08`, also in 2026). Confirm zero
new network calls are made for the holiday source on the subsequent
runs.

**Acceptance Scenarios**:

1. **Given** no cache exists for year Y, **When** the user runs the
   CLI for a month in year Y, **Then** the tool fetches the Hamburg
   holidays for year Y exactly once and writes them to a local cache
   identified by year Y.
2. **Given** a cache for year Y already exists, **When** the user
   runs the CLI for any month in year Y, **Then** the tool reads
   the holiday list from the cache and makes zero network calls
   for holiday data.
3. **Given** a cache for year Y already exists, **When** the user
   runs the CLI for a month in year Y+1, **Then** the year-Y cache
   is preserved untouched and a new cache entry for year Y+1 is
   fetched and written. The two years coexist in the cache.

---

### User Story 2 — The cache survives across runs and across terminals (Priority: P1) 🎯 MVP

The local cache is durable: it persists across CLI invocations, across
terminal sessions, across shell restarts, and across machine reboots.
It is stored at the standard per-user application-data location for
the operating system, so different repositories / clones of the
project share the same cache.

**Why this priority**: A cache that doesn't survive process exit is
just a memo. The whole point is "don't re-query" across an arbitrary
number of future runs.

**Independent Test**: Run the CLI for a month, confirm the cache
file is created, exit the terminal, open a new terminal, run again
— confirm no new network call is made. Repeat after a reboot.

**Acceptance Scenarios**:

1. **Given** the CLI just populated the cache, **When** the user
   closes the terminal and opens a new one, **Then** the next CLI
   run uses the cache from disk and makes no network call for
   holidays.
2. **Given** the cache file exists from an earlier session, **When**
   a different shell or a different working directory invokes the
   CLI for the same year, **Then** that invocation also reads the
   same cache (the cache is per-user, not per-repo).
3. **Given** the user reboots the machine, **When** the CLI is run
   again, **Then** the cache is still present and is still honoured.

---

### User Story 3 — Graceful behaviour when the cache is missing, corrupt, or the source is unreachable (Priority: P2)

The cache pathway must degrade safely. If the cache file is missing
or unreadable, the tool refetches silently. If the holiday source
itself is unreachable AND no cache exists, the tool falls back to the
feature-003 behaviour for an unknown year: no rows marked holiday, no
error raised, the user can still book hours.

**Why this priority**: P2 because the happy path (US1+US2) already
delivers the user's request; this story prevents the feature from
ever making the tool worse than the pre-feature behaviour.

**Independent Test**: Delete the cache file. Disconnect from the
network. Run the CLI. Confirm the tool does NOT crash, does NOT
hang, and does NOT raise a stack trace at the user — instead it
shows the preview without any holiday rows marked (same as feature
003 FR-013).

**Acceptance Scenarios**:

1. **Given** the cache file does not exist and the network is
   reachable, **When** the user runs the CLI, **Then** the tool
   fetches, writes the cache, and proceeds normally.
2. **Given** the cache file exists but is malformed / truncated /
   from a different schema version, **When** the user runs the
   CLI, **Then** the tool treats the cache as a miss, refetches if
   possible, and either rewrites the cache or degrades to the
   no-holidays fallback if the refetch also fails — without
   crashing.
3. **Given** the cache is missing and the network or holiday source
   is unreachable, **When** the user runs the CLI, **Then** the
   preview is shown without any holiday rows marked (same as the
   feature-003 unknown-year fallback) and the user can continue
   booking hours normally.
4. **Given** the cache is present but the source is unreachable,
   **When** the user runs the CLI, **Then** the user sees the
   correct holiday rows from the cache — being offline does not
   degrade behaviour once the cache exists.

---

### Edge Cases

- **Year crossover at midnight**: the cache key is the year of the
  *month being previewed*, NOT "the year right now". A user who, at
  23:59 on 2026-12-31, runs `moco-filler --month 2026-12` must hit
  the 2026 cache; if they run `moco-filler --month 2027-01` at
  00:00, that needs a 2027 cache entry which may not yet exist
  (one-time fetch on first need).
- **Concurrent runs**: two parallel CLI invocations on the same
  machine, both needing the same year on a cold cache, must both
  succeed; the cache write must not corrupt the file if both
  processes try to write at once (atomic write or last-writer-wins
  with consistent content is acceptable; partial-file writes are
  not).
- **Old cache schema**: if a future version of the tool changes the
  on-disk shape of the cache, an existing cache file in the older
  shape must be ignored (treated as a miss) instead of read and
  misinterpreted. The cache file must carry a schema indicator.
- **Read-only filesystem**: if the cache directory cannot be
  written (e.g., a sandboxed CI environment, or a read-only
  filesystem), the tool must still complete the CLI session
  normally — it just won't have a cache for next time. No crash,
  no surfaced error.
- **User wants to force a refresh**: deleting the cache file (or
  the year-Y entry within it) is the supported "force refresh"
  mechanism. No CLI flag is required in v1.
- **A holiday law change mid-year**: if Hamburg amends its public
  holidays inside a calendar year, the cache will hold the
  pre-amendment list until the user explicitly deletes it. This is
  an accepted limitation — explicit cache invalidation is the
  user's tool.
- **An obviously bogus response from the source** (e.g., zero
  holidays returned, or hundreds): the tool may choose to reject
  the response without persisting it; the spec does not require
  validation beyond "the parsed result is structurally well-formed
  for the catalogue's expected shape".

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST fetch the Hamburg public-holiday list
  for the year of the month being previewed from an authoritative
  external source the first time that year is needed in a given
  installation.
- **FR-002**: The system MUST persist the fetched holiday list to a
  local on-disk cache so that it survives process exit, terminal
  closure, and machine reboot.
- **FR-003**: The system MUST NOT issue a new fetch for year Y if a
  valid (non-corrupt, schema-current) cache entry for year Y is
  already present on the user's machine. Re-running the CLI any
  number of times for the same year makes exactly zero additional
  holiday-source requests.
- **FR-004**: The cache MUST be keyed by **(region, year)** —
  Hamburg-only for now, one entry per calendar year — so that
  multiple years can coexist without overwriting each other, and so
  that a future region (per the feature-003 follow-up note) can be
  added without breaking the Hamburg cache.
- **FR-005**: The cache file's location MUST follow the standard
  per-user, per-OS conventions for application data (XDG on Linux,
  the macOS Library directory, the Windows AppData directory), so
  the cache is shared across every clone / working directory of the
  project the user runs from.
- **FR-006**: A missing, unreadable, or schema-incompatible cache
  MUST be treated as a cache miss — the tool refetches transparently
  and never raises a stack trace at the user because of cache state.
- **FR-007**: If the network fetch fails or the source is
  unreachable AND no usable cache exists for the requested year, the
  tool MUST fall back to the feature-003 unknown-year behaviour: no
  rows marked holiday, no error message, the CLI continues normally.
- **FR-008**: If the network fetch is slow, the tool MUST NOT block
  the interactive CLI for longer than 1.5 seconds waiting for the
  holiday source; if the source takes longer, the tool aborts the
  fetch and degrades per FR-007.
- **FR-009**: The cache file MUST contain only public holiday data
  and the metadata needed to read it back (e.g., region, year,
  schema indicator, fetched-at timestamp). It MUST NOT contain any
  API tokens, Moco data, project information, or other user-private
  data.
- **FR-010**: The cache file MUST be a plain user-readable file (not
  encrypted, not opaque) that the user can inspect or delete with
  ordinary OS file-management tools. Deleting the file (or the year
  entry within it) is the supported "force refresh" mechanism.
- **FR-011**: Within one calendar year, the cache MUST NOT auto-
  refresh on its own. A new fetch happens only when (a) no cache
  entry for the requested year exists, (b) the cache entry is
  malformed or schema-incompatible, or (c) the user has manually
  deleted the cache file or its year entry.
- **FR-012**: When the user previews a month in year Y+1 for the
  first time, a *new* cache entry for year Y+1 MUST be created
  alongside any existing year-Y entry, not in place of it.
- **FR-013**: Concurrent CLI invocations on the same machine MUST
  not corrupt the cache file. Either the writes are atomic, or one
  writer wins with structurally valid content; partial writes
  leaving the file unreadable are not acceptable.
- **FR-014**: The cache MUST NOT change the user-visible behaviour
  defined in feature 003 (preview rendering, holiday names, the
  override flow, the already-logged precedence rule). This feature
  is purely a source-and-caching change behind the existing
  holiday API surface.

### Key Entities

- **Holiday cache**: a per-user, on-disk store mapping
  *(region, year)* to a list of *(date, holiday name)* pairs and the
  metadata needed to read it back safely (a schema indicator and a
  fetched-at timestamp). One file, multiple year entries; the file
  grows by one entry per new year the user previews.
- **Holiday-source response (transient)**: the data returned by the
  external authoritative source for a given year. Used to build a
  cache entry, then discarded. Never re-queried for the same year
  on the same machine.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After one successful fetch for year Y, the next ten
  CLI runs for any month in year Y on the same machine make exactly
  zero holiday-source network requests.
- **SC-002**: A CLI run that uses the cache (i.e., not the first run
  for a year) adds no more than 100ms of startup overhead for
  holiday handling versus the pre-feature-003 baseline.
- **SC-003**: A first-run fetch completes in under 1.5 seconds in
  the happy path, and is forcibly bounded at 1.5 seconds in the
  worst case (after which the fallback in FR-007 applies).
- **SC-004**: A user who is offline and has a cache populated for
  the requested year sees the correct holiday rows in the preview
  — being offline does not visibly degrade the tool once the
  cache exists.
- **SC-005**: A user who is offline and has no cache populated for
  the requested year sees the same preview they would have seen
  before feature 003 — i.e., the unknown-year fallback applies,
  no crash, no stack trace.
- **SC-006**: The cache file is below 100KB per supported year for
  the foreseeable list of Hamburg holidays (sanity check; Hamburg
  has on the order of ten holidays per year, so this is a generous
  bound).
- **SC-007**: 100% of the user-visible acceptance scenarios from
  feature 003 (auto-skip, named-holiday row, override flow,
  already-logged precedence, colour fallback) continue to pass
  after this feature is implemented — the source change is
  invisible to existing behaviour.

## Assumptions

- This feature **amends** the assumption in
  `specs/003-hamburg-holidays-skip/spec.md` Assumptions that "the
  holiday catalogue lives in the tool itself ... No network call is
  made to look up holidays". The amended position is: the holiday
  catalogue is **fetched once per year from an authoritative
  source** and **cached locally**. The choice of source is left to
  the implementation plan (`/speckit-plan`).
- The user is online on at least one CLI run per calendar year per
  machine. If that assumption fails, the feature-003 unknown-year
  fallback applies and the tool simply doesn't mark holidays for
  that year on that machine until the user is online once.
- The cache is **per-user, per-machine**. It is not synced across
  machines (no cloud sync), it is not shared between users on a
  multi-user machine, and it is not committed to git. Cross-machine
  sharing is not required because a fresh fetch on a new machine
  is a one-time cost.
- The cache is **per (region, year)**. Region is currently always
  Hamburg per feature 003's scope; the cache layout reserves space
  for additional regions so a future "make region configurable"
  feature doesn't need a cache migration.
- "For the year" in the user's description is interpreted as "for
  the calendar year of the month being previewed". A user who
  bounces between months in the same year fetches at most once;
  a user who bounces between two adjacent years fetches at most
  twice (once per year). This matches the natural reading of "once
  per year".
- The authoritative holiday source is a free, public, anonymous
  endpoint that does not require user authentication. (The choice
  of source — e.g., a public holidays API — is an implementation
  detail decided in `/speckit-plan`, not in this spec.)
- The cache does not introduce any new user-facing CLI flag in v1
  (no `--refresh-holidays`, no `--cache-dir`). Manual cache
  refresh is "delete the file", consistent with FR-010.
- The Questionary-only mandate (Constitution §I), the exit-code
  contract, and the stdout/stderr contract are unchanged by this
  feature.
