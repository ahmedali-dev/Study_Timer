"""SQLite storage for task-specific timer plans."""

import os
from pathlib import Path
import sqlite3
import sys
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
import json


def default_database_path():
    override = os.environ.get("FOCUSNEST_DATA_DIR") or os.environ.get("STUDY_TIMER_DATA_DIR")
    if override:
        return Path(override) / "study_timer.sqlite3"
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent.parent / "data" / "study_timer.sqlite3"
    if sys.platform == "win32":
        folder = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        folder = Path.home() / "Library" / "Application Support"
    else:
        folder = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    # Preserve the deployed storage path across the FocusNest rename.
    return folder / "StudyTimer" / "study_timer.sqlite3"


class TaskStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else default_database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Preserve a recoverable copy before upgrading an existing database.
        if self.path.exists():
            with self._connect() as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                has_tasks = connection.execute("SELECT 1 FROM sqlite_master WHERE name='tasks'").fetchone()
                backup_path = self.path.with_suffix(".pre-v1.bak")
                if version == 0 and has_tasks and not backup_path.exists():
                    with sqlite3.connect(backup_path) as backup:
                        connection.backup(backup)
        with self._connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            if connection.execute("PRAGMA user_version").fetchone()[0] > 1:
                raise ValueError("This database requires a newer version of FocusNest.")
            connection.execute("""CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 160),
                focus_minutes INTEGER NOT NULL CHECK(focus_minutes > 0),
                break_minutes INTEGER NOT NULL CHECK(break_minutes >= 0),
                sessions INTEGER NOT NULL CHECK(sessions > 0),
                completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                deleted_at TEXT
            )""")
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
            if "deleted_at" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN deleted_at TEXT")
            if "planned_date" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN planned_date TEXT")
                for row in connection.execute("SELECT id, created_at FROM tasks").fetchall():
                    try:
                        created = datetime.fromisoformat(row['created_at'])
                        if created.tzinfo is None:
                            created = created.replace(tzinfo=timezone.utc)
                        day = created.astimezone().date().isoformat()
                    except (ValueError, TypeError):
                        day = date.today().isoformat()
                    connection.execute("UPDATE tasks SET planned_date=? WHERE id=?", (day, row['id']))
            if "priority" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN priority INTEGER NOT NULL DEFAULT 1 CHECK(priority BETWEEN 0 AND 2)")
            if "final_break" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN final_break INTEGER NOT NULL DEFAULT 1 CHECK(final_break IN (0,1))")
            for statement in (
                "CREATE INDEX IF NOT EXISTS tasks_plan_idx ON tasks(planned_date,completed,priority)",
                "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
                """CREATE TABLE IF NOT EXISTS timer_runs (
                    id TEXT PRIMARY KEY, task_id INTEGER, title TEXT NOT NULL,
                    focus_minutes INTEGER NOT NULL, break_minutes INTEGER NOT NULL,
                    sessions INTEGER NOT NULL, final_break INTEGER NOT NULL,
                    status TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT)""",
                "CREATE TABLE IF NOT EXISTS active_timer (id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL)",
                """CREATE TABLE IF NOT EXISTS focus_sessions (
                    run_id TEXT NOT NULL, session_index INTEGER NOT NULL, status TEXT NOT NULL,
                    ended_at TEXT NOT NULL, PRIMARY KEY(run_id,session_index))""",
                """CREATE TABLE IF NOT EXISTS focus_intervals (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, session_index INTEGER NOT NULL,
                    started_at TEXT NOT NULL, ended_at TEXT NOT NULL, seconds REAL NOT NULL CHECK(seconds>=0))""",
                "CREATE INDEX IF NOT EXISTS focus_intervals_date_idx ON focus_intervals(ended_at)",
                "CREATE INDEX IF NOT EXISTS timer_runs_task_idx ON timer_runs(task_id,started_at)",
                """CREATE TABLE IF NOT EXISTS task_completions (
                    id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL, completed_at TEXT NOT NULL,
                    reversed INTEGER NOT NULL DEFAULT 0)""",
            ):
                connection.execute(statement)
            connection.execute("PRAGMA user_version=1")

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def validate(title, focus_minutes, break_minutes, sessions):
        title = title.strip()
        if not 1 <= len(title) <= 160:
            raise ValueError("Enter a task name between 1 and 160 characters.")
        values = []
        for value in (focus_minutes, break_minutes, sessions):
            if isinstance(value, bool) or not isinstance(value, (int, str)):
                raise ValueError("Timer settings must be whole numbers.")
            try:
                number = int(value)
            except ValueError:
                raise ValueError("Timer settings must be whole numbers.") from None
            if number > 2147483647:
                raise ValueError("Timer settings are too large.")
            values.append(number)
        if values[0] <= 0 or values[1] < 0 or values[2] <= 0:
            raise ValueError("Focus time and sessions must be positive. Break time can be zero.")
        return (title, *values)

    def save(self, title, focus_minutes, break_minutes, sessions, task_id=None, planned_date=None, priority=1, final_break=True):
        values = self.validate(title, focus_minutes, break_minutes, sessions)
        if priority not in (0, 1, 2):
            raise ValueError("Choose a valid priority.")
        if planned_date is None and task_id is not None:
            existing = self.get(task_id)
            planned_date = existing['planned_date'] if existing else None
        try:
            planned_date = date.fromisoformat(planned_date or date.today().isoformat()).isoformat()
        except (ValueError, TypeError):
            raise ValueError("Choose a valid planned date (YYYY-MM-DD).") from None
        values = (*values, planned_date, priority, int(bool(final_break)))
        with self._connect() as connection:
            if task_id is None:
                result = connection.execute(
                    "INSERT INTO tasks (title, focus_minutes, break_minutes, sessions, planned_date, priority, final_break) VALUES (?, ?, ?, ?, ?, ?, ?)", values)
                return result.lastrowid
            result = connection.execute(
                "UPDATE tasks SET title=?, focus_minutes=?, break_minutes=?, sessions=?, planned_date=?, priority=?, final_break=? WHERE id=? AND deleted_at IS NULL", (*values, task_id))
            if not result.rowcount:
                raise ValueError("This task no longer exists.")
            return task_id

    def list_tasks(self, search='', status='all', priority=None, planned_date=None):
        with self._connect() as connection:
            clauses, params = ['deleted_at IS NULL'], []
            if status in ('pending', 'completed'):
                clauses.append('completed=?')
                params.append(int(status == 'completed'))
            if priority is not None:
                clauses.append('priority=?')
                params.append(int(priority))
            if planned_date:
                clauses.append('planned_date=?')
                params.append(planned_date)
            rows = [dict(row) for row in connection.execute(
                """SELECT tasks.*, (SELECT COUNT(*) FROM focus_sessions WHERE status='completed' AND run_id=
                    (SELECT id FROM timer_runs WHERE task_id=tasks.id ORDER BY started_at DESC LIMIT 1)) AS completed_rounds,
                    (SELECT sessions FROM timer_runs WHERE task_id=tasks.id ORDER BY started_at DESC LIMIT 1) AS last_run_sessions
                    FROM tasks WHERE """ + ' AND '.join(clauses) + ' ORDER BY completed, priority DESC, id DESC', params)]
            # Python casefold supports Unicode and treats SQL wildcards literally.
            if search:
                rows = [row for row in rows if search.casefold() in row['title'].casefold()]
            return rows

    def get(self, task_id):
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id=? AND deleted_at IS NULL", (task_id,)).fetchone()
            return dict(row) if row else None

    def set_completed(self, task_id, completed):
        with self._connect() as connection:
            previous = connection.execute("SELECT completed FROM tasks WHERE id=? AND deleted_at IS NULL", (task_id,)).fetchone()
            result = connection.execute("UPDATE tasks SET completed=? WHERE id=? AND deleted_at IS NULL", (int(bool(completed)), task_id))
            if not result.rowcount:
                raise ValueError("This task no longer exists.")
            if completed and previous and not previous['completed']:
                connection.execute("INSERT INTO task_completions(task_id,completed_at) VALUES (?,?)", (task_id, utc_now()))
            elif not completed:
                connection.execute("UPDATE task_completions SET reversed=1 WHERE task_id=?", (task_id,))

    def delete(self, task_id):
        """Hide a task while keeping its data available for Undo."""
        with self._connect() as connection:
            result = connection.execute(
                "UPDATE tasks SET deleted_at=CURRENT_TIMESTAMP WHERE id=? AND deleted_at IS NULL", (task_id,))
            if not result.rowcount:
                raise ValueError("This task no longer exists.")

    def restore(self, task_id):
        with self._connect() as connection:
            result = connection.execute(
                "UPDATE tasks SET deleted_at=NULL WHERE id=? AND deleted_at IS NOT NULL", (task_id,))
            if not result.rowcount:
                raise ValueError("This task could not be restored.")

    def load_settings(self):
        with self._connect() as connection:
            return {row['key']: json.loads(row['value']) for row in connection.execute('SELECT * FROM settings')}

    def save_settings(self, values):
        with self._connect() as connection:
            connection.executemany('INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)',
                                   [(key, json.dumps(value)) for key, value in values.items()])

    def active(self):
        with self._connect() as connection:
            row = connection.execute('SELECT state FROM active_timer WHERE id=1').fetchone()
            if not row:
                return None
            state = json.loads(row['state'])
            if not isinstance(state, dict):
                raise ValueError('Invalid saved timer state.')
            return state

    def discard_invalid_checkpoint(self):
        """Explicit recovery action: retain all history and only end active runs."""
        with self._connect() as connection:
            connection.execute("UPDATE timer_runs SET status='interrupted',ended_at=? WHERE status='active'", (utc_now(),))
            connection.execute('DELETE FROM active_timer')

    def create_run(self, state):
        with self._connect() as connection:
            if connection.execute('SELECT 1 FROM active_timer').fetchone():
                raise ValueError('Resume or discard the saved session first.')
            connection.execute('INSERT INTO timer_runs VALUES (?,?,?,?,?,?,?,?,?,?)',
                (state['run_id'], state['task_id'], state['title'], state['focus_minutes'], state['break_minutes'],
                 state['sessions'], int(state['final_break']), 'active', state['started_at'], None))
            connection.execute('INSERT INTO active_timer VALUES (1,?)', (json.dumps(state),))

    def checkpoint(self, state, intervals=(), session_result=None, outcome=None):
        with self._connect() as connection:
            connection.executemany('INSERT OR IGNORE INTO focus_intervals VALUES (?,?,?,?,?,?)', intervals)
            if session_result:
                connection.execute('INSERT OR REPLACE INTO focus_sessions VALUES (?,?,?,?)', session_result)
            if outcome:
                connection.execute('UPDATE timer_runs SET status=?,ended_at=? WHERE id=?', (outcome, utc_now(), state['run_id']))
                connection.execute('DELETE FROM active_timer WHERE id=1')
                if outcome == 'completed' and not state['skipped'] and state['task_id'] is not None:
                    task = connection.execute('SELECT completed FROM tasks WHERE id=? AND deleted_at IS NULL', (state['task_id'],)).fetchone()
                    if task and not task['completed']:
                        connection.execute('UPDATE tasks SET completed=1 WHERE id=?', (state['task_id'],))
                        connection.execute('INSERT INTO task_completions(task_id,completed_at) VALUES (?,?)', (state['task_id'], utc_now()))
            else:
                connection.execute('INSERT OR REPLACE INTO active_timer VALUES (1,?)', (json.dumps(state),))

    def history(self, task_id=None):
        with self._connect() as connection:
            query = """SELECT r.*, COALESCE((SELECT SUM(seconds) FROM focus_intervals WHERE run_id=r.id),0) AS focus_seconds,
                (SELECT COUNT(*) FROM focus_sessions WHERE run_id=r.id AND status='completed') AS completed_sessions
                FROM timer_runs r"""
            return [dict(row) for row in connection.execute(query + (' WHERE task_id=?' if task_id is not None else '') + ' ORDER BY started_at DESC', (task_id,) if task_id is not None else ())]

    def daily_stats(self, days=7, today=None, local_timezone=None):
        today = today or date.today()
        totals = {(today - timedelta(days=i)).isoformat(): dict(focus_seconds=0.0, sessions=0, tasks=0) for i in range(days)}
        def local(value):
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(local_timezone)
        with self._connect() as connection:
            for row in connection.execute('SELECT * FROM focus_intervals'):
                start, end = local(row['started_at']), local(row['ended_at'])
                # Find midnight in each calendar day, converting separately for DST.
                start_utc, end_utc = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
                span = (end_utc - start_utc).total_seconds()
                if span <= 0:
                    continue
                cursor = start_utc
                while cursor < end_utc:
                    current = cursor.astimezone(local_timezone)
                    next_date = current.date() + timedelta(days=1)
                    midnight = datetime.combine(next_date, time.min)
                    boundary = (midnight.replace(tzinfo=local_timezone) if local_timezone else midnight.astimezone()).astimezone(timezone.utc)
                    stop = min(boundary, end_utc)
                    key = current.date().isoformat()
                    if key in totals:
                        totals[key]['focus_seconds'] += row['seconds'] * (stop - cursor).total_seconds() / span
                    cursor = stop
            for row in connection.execute("SELECT ended_at FROM focus_sessions WHERE status='completed'"):
                key = local(row['ended_at']).date().isoformat()
                if key in totals:
                    totals[key]['sessions'] += 1
            for row in connection.execute('SELECT completed_at FROM task_completions WHERE reversed=0'):
                key = local(row['completed_at']).date().isoformat()
                if key in totals:
                    totals[key]['tasks'] += 1
        return totals

    def history_for_day(self, day, local_timezone=None):
        """Per-run actual work on a local day, including runs crossing midnight."""
        day = date.fromisoformat(day)
        def boundary(value):
            naive = datetime.combine(value, time.min)
            return (naive.replace(tzinfo=local_timezone) if local_timezone else naive.astimezone()).astimezone(timezone.utc)
        start, end = boundary(day), boundary(day + timedelta(days=1))
        seconds, rounds = {}, {}
        with self._connect() as connection:
            for row in connection.execute('SELECT * FROM focus_intervals WHERE ended_at>=? AND started_at<?', (start.isoformat(), end.isoformat())):
                first, last = datetime.fromisoformat(row['started_at']), datetime.fromisoformat(row['ended_at'])
                span = (last - first).total_seconds()
                overlap = max(0, (min(last, end) - max(first, start)).total_seconds())
                if span > 0 and overlap > 0:
                    seconds[row['run_id']] = seconds.get(row['run_id'], 0) + row['seconds'] * overlap / span
            for row in connection.execute("SELECT run_id,COUNT(*) AS count FROM focus_sessions WHERE status='completed' AND ended_at>=? AND ended_at<? GROUP BY run_id", (start.isoformat(), end.isoformat())):
                rounds[row['run_id']] = row['count']
        results = []
        for run in self.history():
            began = datetime.fromisoformat(run['started_at'])
            if run['id'] in seconds or run['id'] in rounds or start <= began < end:
                results.append({**run, 'focus_seconds': seconds.get(run['id'], 0), 'completed_sessions': rounds.get(run['id'], 0)})
        return results


def utc_now():
    return datetime.now(timezone.utc).isoformat()
