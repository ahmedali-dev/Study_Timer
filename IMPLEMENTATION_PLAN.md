# Study Timer improvement plan

Status: implementation in progress. Phases 1–6 now have application code and automated coverage; desktop smoke tests and release hardening are ongoing. Phase 7 has pinned build tools, a local build script, Windows installer configuration, and native CI jobs. Public signing/notarization, clean-machine verification, and native Windows/Linux release validation remain outstanding. See `packaging/README.md` for build instructions and release boundaries.

## Goal and delivery order

Make Study Timer reliable across restarts, useful for daily planning, and easy to install on Windows, macOS, and Linux.

Deliver in seven phases:

1. Save and restore timer progress.
2. Add planned task dates.
3. Track completed sessions and actual focus time.
4. Show daily progress.
5. Improve timer controls.
6. Add priorities and search.
7. Package and distribute desktop builds.

Each phase should leave the app usable and pass its acceptance checks before the next phase starts. Phase 4 depends on the activity records from phase 3; phase 5 must use the same timer state and history model established in phases 1 and 3.

## Current foundation

- Flet provides the desktop interface and timer controls.
- `src/main.py` owns an in-memory countdown, pause state, audio, and notifications.
- `src/task_store.py` stores tasks in SQLite, including their timer plans, completion state, creation timestamps, and recoverable deletion.
- `src/TaskList.py` provides task editing and collapsible groups based on local creation dates.
- Cross-platform notifications and task storage already have automated checks.

The main gap is that timer state and actual work history disappear when the process ends. Existing task rows describe a plan, not time already spent.

## Shared implementation rules

- Preserve existing tasks and settings through versioned, transactional database migrations. Back up the database before a migration that transforms existing records.
- Use SQLite `PRAGMA user_version` to track schema versions; test upgrades from the current database and repeated startup after migration.
- Use UTC timestamps for events, local `YYYY-MM-DD` values for planned dates, and timezone-aware conversion for display and reporting.
- Keep database writes outside the UI rendering code. Use short transactions, parameterized SQL, and separate connections for worker threads.
- Extract timer behavior into a controller with an injectable clock so state transitions can be tested without waiting through real sessions.
- A run keeps a snapshot of its original timer plan. Editing a task affects future runs, not an active or recoverable run.
- Audio and notification failures must never interrupt the timer or prevent state persistence.
- Show storage failures visibly. Do not claim that progress was saved when a write failed.
- Keep soft-deleted tasks out of normal task views, but preserve their historical work records.

## Phase 1 — Save timer progress

### User experience

- Save the active task, current focus/break phase, session number, remaining seconds, and paused state.
- On launch, offer **Resume session** or **Discard session** when unfinished progress exists. Show the task name and remaining time before the choice.
- Restore into a paused state so the timer never starts unexpectedly.
- Time while the app is closed does not count as focus or break time.
- A normal close checkpoints immediately. A crash may lose at most the last five seconds since the previous successful checkpoint.
- Treat a long suspension or system sleep as an interruption; return paused at the last reliable checkpoint rather than crediting unobserved time.

### Implementation

- Introduce a timer controller for start, pause, resume, stop, and phase transitions. Keep the existing screen as its view.
- Add a `timer_runs` table with a unique run ID, optional task ID, task-name snapshot, planned focus/break durations, planned session count, status, and start/end timestamps.
- Add a singleton `active_timer` checkpoint referencing the run, including phase, session index, remaining seconds, paused state, and checkpoint timestamp.
- Store ordinary timer runs too, even when no task is selected.
- Use a monotonic clock while the app is running; never serialize a monotonic deadline for use after restart.
- Checkpoint every five seconds and immediately on pause, resume, phase changes, and window close.
- Save phase transitions and their checkpoints together in one transaction.
- Resume the same run ID rather than creating a duplicate run. Stop/discard marks the run interrupted and clears its active checkpoint.
- If the original task was deleted, offer to resume its saved timer plan without restoring or completing the deleted task.
- Prevent two app instances from simultaneously owning the same active timer, using a process lock or equivalent single-instance mechanism.

### Acceptance checks

- Close and reopen during focus, during a break, and while paused; recover the correct task, phase, session, and time.
- Force termination and verify the bounded checkpoint loss.
- Closing the app for an hour does not consume the remaining timer.
- Simulate sleep, invalid checkpoints, deleted tasks, and unavailable storage without crashing.
- Repeated resume actions create one worker and one run; a second app instance cannot start another owner.

## Phase 2 — Add planned dates

### User experience

- Add a **Planned date** picker when creating or editing a task; default new tasks to today.
- Group tasks by their planned date rather than their creation date.
- Today's group opens by default; other dates start collapsed and remain manually expandable.
- Label nearby dates as Today, Tomorrow, and Yesterday; show the actual calendar date alongside them.
- Mark unfinished past-dated tasks as overdue and provide **Move to today**.
- Recalculate the current day when the app regains focus or passes midnight.

### Implementation

- Add `tasks.planned_date` and an index supporting date-based listing.
- Backfill existing tasks from each creation timestamp converted to the user's local calendar date, preserving existing grouping as closely as possible.
- Store planned dates as date-only strings; a timezone change must not shift a scheduled task to another date.
- Keep creation timestamps unchanged for audit/history purposes.
- Extend task validation, editing, grouping, and SQLite queries to support the new field.

### Acceptance checks

- Create and move tasks across yesterday, today, tomorrow, and a later date.
- Verify today's default expansion and older/future default collapse.
- Reopen the app and confirm planned dates persist.
- Check midnight and timezone changes, including tasks created near UTC midnight.
- Existing tasks retain their names, plans, completion state, and deletion state after migration.

## Phase 3 — Track sessions and actual focus time

### User experience

- Show task progress such as **2 of 4 focus sessions completed**.
- Keep partial focus time when the user stops early.
- Add a task history view showing dated runs, focus time, completed sessions, and whether a run finished or was interrupted.
- Completing or reopening a task manually must not fabricate or erase focus time.

### Implementation

- Extend `timer_runs` with completion outcome and the final-break preference snapshot.
- Add `focus_sessions` records keyed by run and session index, with status, start/end timestamps, and accumulated active seconds.
- Add `focus_intervals` for credited, unpaused work segments. Use these as the source of truth for actual time and daily totals.
- Persist active intervals with the existing checkpoint transaction; pause, break, stop, and close end an interval.
- Mark a session completed only when its planned focus countdown reaches zero. Partial or skipped sessions retain time but are not completed sessions.
- Use unique run/session identifiers and idempotent writes to prevent double-counting after recovery.
- Add task-completion events so manual completion and automatic completion can be dated separately from focus history. Reopening reverses the associated completion event rather than adding a second completion.
- Aggregate progress per run; starting a new run starts its own session count while preserving previous history.
- Do not invent historical work for pre-existing completed tasks; label their earlier completion date as unknown if necessary.

### Acceptance checks

- Focus time increases only while actively focusing, excluding pauses, breaks, and offline time.
- Stop halfway through a focus session: actual time is retained, completed-session count stays unchanged.
- Restart and recover a run multiple times without duplicating time or sessions.
- Mark a task complete manually and reopen it; history remains intact and completion counts stay consistent.
- Deleted tasks disappear from the list but their legitimate focus history remains available to reporting.

## Phase 4 — Show daily progress

### User experience

- Add a compact Today overview with actual focus minutes, completed focus sessions, and completed tasks.
- Show a seven-day focus-time chart and a daily breakdown below it.
- Let users inspect a day or open its related tasks/history.
- Provide an informative empty state before any activity exists.

### Implementation

- Build statistics queries from phase 3's intervals, session outcomes, and completion events, rather than task duration multiplied by planned sessions.
- Split active intervals across local day boundaries before summing. Account for timezone offsets and daylight-saving transitions.
- Count a completed focus session on the day it finishes. Count each non-reversed task completion once.
- For the initial release, show historical activity in the device's current local timezone and state this in the reporting UI.
- Refresh totals after relevant events, on app resume, and at midnight.
- Add indexes for timestamp ranges and task/run lookups. Compute totals on demand first; add cached aggregates only if profiling shows a need.

### Acceptance checks

- Known sample history yields the exact expected daily totals.
- Paused time, breaks, interrupted sessions, and reversed completion events do not inflate results.
- A focus interval crossing midnight is divided between the correct days.
- Timezone and daylight-saving boundary cases produce consistent totals.
- Reopening the app gives the same totals as before closing it.

## Phase 5 — Improve timer controls

### User experience

- During a break, provide **Skip break** to begin the next focus session immediately.
- During focus, provide **Next session**, with confirmation if focus time remains; clearly indicate that the current session will be skipped.
- Add **Take a break after the final session** to task plans and the ordinary timer setup.
- For existing tasks, preserve the current final-break behavior by default; users can turn it off.
- Keep Pause/Resume and End session available and clearly labeled.

### Implementation

- Add a final-break setting to task plans, normal timer preferences, and run snapshots.
- Implement skip and next actions as controller transitions, not additional countdown threads.
- Define Next session as skipping the remaining focus time and its associated break to begin the next focus round; if no round remains, end the run as incomplete/skipped.
- Skipped focus retains actual time already spent but does not count as a completed focus session or automatically complete the task.
- Skipping the final break ends a run normally if every focus session finished.
- With final break disabled, complete the run as soon as the last focus session finishes.
- Checkpoint every action atomically and send the appropriate transition notification once.

### Acceptance checks

- Cover zero-minute breaks, one-session plans, final-break on/off, skip while paused, and repeated button presses.
- Ensure only one timer worker remains active.
- Verify skipping never inflates focus/session counts or completes an unfinished task.
- Restart immediately after a skip and recover the correct next state.

## Phase 6 — Add task priorities and search

### User experience

- Add Low, Normal, and High priority to task editing; default existing tasks to Normal.
- Show a small labeled priority badge, with color as a secondary cue.
- Add a task-name search field and filters for status, planned date, and priority.
- Keep date grouping; within each group, show pending tasks before completed tasks, then sort by priority and a stable creation order.
- Show a clear **No matching tasks** state and a way to clear filters.

### Implementation

- Add a validated `tasks.priority` value and indexes guided by actual queries.
- Use parameterized queries for text and filters, excluding soft-deleted tasks.
- Treat search characters literally when building substring matches; escape SQL wildcard characters.
- Search case-insensitively for supported text and verify behavior with non-Latin task names; document any SQLite collation limitations before claiming full Unicode case folding.
- Debounce input and avoid rendering stale results from earlier searches.
- Show filtered counts separately from overall daily statistics.

### Acceptance checks

- Priority and filter selections survive the relevant save/reload flow.
- Combine text, date, completion, and priority filters.
- Search punctuation, quotes, percent signs, underscores, and Arabic task names.
- Clearing search restores date groups and their expected expansion behavior.
- Verify responsiveness with a realistic large task dataset.

## Phase 7 — Package desktop releases

### User experience

- Launch from an app icon without installing Python or using a terminal.
- Deliver a Windows installer, macOS app distribution, and Linux package appropriate to the chosen release channel.
- Preserve tasks, settings, and recoverable timer progress across upgrades.
- Show the app version and provide a documented database backup location.

### Implementation

- Consolidate runtime dependency declarations and verify the packaging approach against the pinned Flet version before choosing final build commands.
- Separate bundled read-only assets from writable user data. Move remaining timer/music preferences into a writable settings store, migrating any supported legacy JSON settings.
- Use the platform-specific user data paths already supported by task storage; never write into an installed app bundle.
- Build on native Windows, macOS, and Linux CI runners. Verify bundled icons, audio, SQLite support, and native notification backends.
- Test notifications in packaged apps; macOS script-host notifications may need replacement with an app-identified native backend for a polished signed release.
- Handle missing Linux notification services/tools gracefully and document any required system package.
- Configure app identity, versioning, icons, and release artifacts consistently.
- Plan signing/notarization where needed. Prepare and test builds before any publication; publishing and paid signing accounts remain separate release decisions.
- Start with manual download-and-install upgrades; defer automatic updating until the release process is reliable.

### Acceptance checks

- Install and launch on clean machines without development dependencies.
- Create tasks, start a timer, close, reopen, and recover on every supported OS.
- Upgrade from an older build and verify that migrations preserve user data.
- Test audio, notifications, permissions, missing optional services, and read-only installation folders.
- Confirm uninstall/reinstall behavior is documented and does not unexpectedly remove user data.

## Completion criteria

The work is complete when all seven phases meet their acceptance checks, existing notification/task tests still pass, and desktop smoke tests cover the full workflow: plan a task, start it, pause, restart the app, recover, finish or skip, inspect accurate daily progress, search the task, and install an upgrade without losing data.

The first implementation should be phase 1's controller, database migration, and recovery flow. That establishes the state model used by session history, reporting, and advanced timer controls.
