# Implementation status — 0.2.0

## Delivered

- Timer controller with five-second checkpoints, immediate pause/close saves, paused restart recovery, interrupted-run handling, sleep detection, and a single-instance lock.
- SQLite schema version 1, transactional migration, pre-migration backup, and preferences imported from supported legacy JSON settings.
- Planned task dates, a calendar picker, date grouping, overdue indicators, and Move to today.
- Actual focus intervals, completed/skipped/partial session records, task completion events, and per-task run history.
- Progress screen with today's totals, a seven-day chart, selectable daily activity, and recent runs. Midnight splitting and daylight-saving boundaries have automated coverage.
- Skip break, confirmed Next session, and optional final breaks. Skipped rounds never count as completed focus sessions.
- Priorities, Unicode-aware literal substring search, status/date/priority filters, and debounced text input.
- Native build workflow definitions, isolated build script, macOS app/ZIP/DMG, Windows Inno Setup configuration, and Linux Debian packaging configuration.

Existing task plans, soft deletion, Undo, and cross-platform notification support remain available.

## Verification performed

- 37 automated tests pass in the isolated project build environment.
- Tests include old-schema migration and rollback/backup, persistence, validation, deletion/Undo, recovery, crash checkpoint limits, sleep handling, partial work, skip behavior, final-break settings, duplicate checkpoint protection, second-instance rejection, Unicode search, date grouping, midnight accounting, and daylight-saving accounting.
- Live desktop check: paused at 00:56, restarted, observed the recovery prompt at 00:56, and restored the timer paused.
- Live desktop check: Progress showed the interrupted run's actual partial focus time; selecting today displayed the matching history.
- Live desktop check: task editor exposed planned date, priority, and final-break controls.
- Packaged macOS app launched and saved a task in a separate temporary test database. No sample task was inserted into the regular user database.
- Latest source app closed cleanly without the older Flet shutdown scheduling error.
- Final macOS build completed with `.app`, `.zip`, and `.dmg` output.

The packaged-app launch test used an earlier build of this same implementation pass. The final rebuild includes the subsequent clean-close, audio-resume, and daily-history refinements; those were exercised in the source app and automated tests. A full final-artifact and clean-machine pass remains a release requirement.

## Final local build artifacts

Folder: `dist/darwin-arm64-20261017-215439-470956/`

- `StudyTimer.app`
- `StudyTimer-0.2.0-darwin-arm64.zip`
- `StudyTimer-0.2.0-darwin-arm64.dmg`

These builds target Apple Silicon. They are not signed with a distribution identity or notarized.

## Remaining release work

- Run native Windows and Linux jobs and verify the generated installer/package on clean machines. CI definitions are local files; no remote workflow or release was created.
- Verify the final macOS artifact after extraction/installation on a clean machine, including notification permissions and audio.
- Configure distribution signing/notarization and app-identified macOS notifications before public distribution.
- Check upgrades over an installed previous build, installer shortcuts, user-data retention, and OS-specific dependencies.
- Profile large task/history collections before claiming scale targets; task filtering supports Unicode but is currently performed in memory after SQLite status/date/priority filtering.
- Further refine keyboard/accessibility behavior and small-window layouts through broader native testing.

The application features are implemented, but phase 7's public-release completion criteria have not yet been met. See `packaging/README.md` for build and data-location instructions.
