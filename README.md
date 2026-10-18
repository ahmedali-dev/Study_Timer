# FocusNest

<img src="src/assets/focusnest-icon.png" width="96" alt="FocusNest FN logo" />

A warm, calm focus timer with scheduled tasks, recoverable sessions, and local progress tracking.

**Rust edition (0.3.0):** the new Tauri + Rust + React application lives separately in [focusnest_rust](focusnest_rust/README.md). See its [native build instructions](focusnest_rust/BUILD.md). The Python/Flet version and its data remain intact; importing into the Rust app is explicit and one-way.

**Build on macOS, Windows, or Linux:** follow [BUILD.md](BUILD.md).

### New in 0.2.0

- Recover unfinished timers after restarting. A saved session restores paused; time while the app is closed is excluded. Progress checkpoints every five seconds and on pause/close.
- Schedule tasks with a planned date, choose a priority, search names, and filter by date/status/priority. Today's group opens by default; other dates start collapsed. Overdue tasks can be moved to today.
- Keep actual focus time and session history, including interrupted work. Pauses, breaks, and time offline never count as focused time.
- Inspect the Progress tab for today's focused minutes, completed sessions/tasks, a seven-day chart, and recent activity. Historical totals are displayed in the current local timezone. Existing completed tasks are not assigned invented historical dates.
- Skip breaks or advance to the next focus session. Skipped focus rounds keep their partial time but do not count as complete. The final break is optional per task or ordinary timer plan.
- Settings now persist in SQLite. Existing JSON preferences are imported on first use. A schema upgrade preserves task data and creates a migration backup.

For packaged desktop apps and installer instructions, see [packaging/README.md](packaging/README.md).
Run all checks with `python -m unittest discover -s tests -v`.

## ✅ Features
### ⏱️ Customizable Pomodoro Sessions
Set your preferred study time, break duration, and the number of sessions.

### 🎵 Background Music for Studying
Play relaxing music during study periods to stay in the zone.

### 🔔 Sound Notifications

Alert when break time starts

Alert when it’s time to resume studying

This tool is designed to help you stay focused, reduce burnout, and build better study habits.

### Desktop notifications

Notifications are sent when focus starts, a break starts, and all sessions finish.
They run in the background, so unavailable or disabled notifications never stop
the timer. Open **Sound & notifications** from the settings button and select
**Test notification** to check your setup. A successful submission means the OS
accepted the request; Focus/Do Not Disturb settings can still hide the banner.

- **Windows:** uses Plyer's Windows notification backend and the bundled `.ico`.
  Install the project dependencies with `python -m pip install -r requirements.txt`.
  Allow notification banners in Windows settings. When packaging with PyInstaller,
  include `--hidden-import=plyer.platforms.win.libs.balloontip` and the assets folder.
- **macOS:** uses the built-in `osascript` notification command; no `pyobjus` is
  needed. Allow notifications for the script host (often Script Editor) in
  System Settings > Notifications if prompted, and check Focus settings.
- **Linux:** uses `notify-send` and requires a graphical desktop with a running
  notification service. Install `libnotify-bin` on Debian/Ubuntu or `libnotify`
  on Fedora/Arch. Headless sessions cannot display desktop banners.

Run notification backend checks with `python -m unittest discover -s tests`.

### To-do list & SQLite

Open the **To-do list** tab and choose **Add task**. Every task stores its own
name, focus minutes, break minutes, and number of sessions. Use **Edit** to adjust
the plan, the checkbox to mark it complete or reopen it, and **Start** to run its
saved timer. Finishing every session automatically completes the task; ending a
timer early leaves it pending. Completed tasks can be unchecked to work on them again.

Tasks are grouped by planned date, newest date first. Existing tasks inherit their local creation date during migration.
Today's group starts expanded; other dates start collapsed. Click a date header
to open or close it. Use the trash button to delete a task and **Undo** in the
confirmation bar to restore it. Deleted tasks are hidden and retained in SQLite
so Undo preserves the full task plan.

Tasks persist between app launches in SQLite, using Python's built-in `sqlite3`
module. In development the database is `data/study_timer.sqlite3`, relative to the
project rather than the launch directory. Packaged apps use the user's application
data folder on Windows, macOS, or Linux. Set `FOCUSNEST_DATA_DIR` to choose another
data folder. Back up the database file while the app is closed to preserve your tasks.
The legacy `STUDY_TIMER_DATA_DIR` override and `StudyTimer` storage folder remain supported to preserve existing data.

### 🧑‍💻 How to Use
Set your study time, break time, and number of sessions.

Choose background music and sound notifications.

Start the timer and focus on your study!

### Legacy preview

These screenshots show the original Study Timer interface, before the FocusNest branding and sidebar redesign.
>>
![2025-06-09 06_20_59-Study Timer](https://github.com/user-attachments/assets/2fb4050d-167a-4491-a490-572aa0a4c92d)
>>
![2025-06-09 06_21_08-Study Timer](https://github.com/user-attachments/assets/2889d74e-1ab1-49ad-abf7-19ba0780de75)
>>
![2025-06-09 06_20_30-Study Timer](https://github.com/user-attachments/assets/7a9f67c3-f205-44fa-86c5-7f70acda27d3)

