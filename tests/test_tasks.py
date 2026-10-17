import itertools
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from task_store import TaskStore
from TaskList import TaskList, group_tasks_by_date
import main


class TaskStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'tasks.sqlite3'
        self.store = TaskStore(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def test_task_and_edits_survive_reopening_database(self):
        task_id = self.store.save("  Read chapter 1  ", '25', '5', '3')
        reopened = TaskStore(self.path)
        task = reopened.get(task_id)
        self.assertEqual((task['title'], task['focus_minutes'], task['break_minutes'], task['sessions']), ('Read chapter 1', 25, 5, 3))
        reopened.save('Review notes', 15, 0, 2, task_id)
        self.assertEqual(self.store.get(task_id)['title'], 'Review notes')
        self.assertEqual(self.store.get(task_id)['sessions'], 2)

    def test_completion_can_be_reversed_and_is_persisted(self):
        task_id = self.store.save('Read', 25, 5, 4)
        self.store.set_completed(task_id, True)
        self.assertEqual(TaskStore(self.path).get(task_id)['completed'], 1)
        self.store.set_completed(task_id, False)
        self.assertEqual(self.store.get(task_id)['completed'], 0)

    def test_invalid_input_creates_no_task(self):
        for title, focus, breaks, sessions in [('', 25, 5, 4), ('x', 0, 5, 4), ('x', 25, -1, 4), ('x', 25, 5, 0), ('x', '1.5', 5, 4), ('x', 25, 5, 'abc'), ('x' * 161, 25, 5, 4)]:
            with self.subTest(values=(title, focus, breaks, sessions)), self.assertRaises(ValueError):
                self.store.save(title, focus, breaks, sessions)
        self.assertEqual(self.store.list_tasks(), [])

    def test_titles_are_stored_as_data(self):
        title = "Read 'notes'; DROP TABLE tasks; --"
        task_id = self.store.save(title, 25, 5, 4)
        self.assertEqual(self.store.get(task_id)['title'], title)
        self.assertEqual(len(self.store.list_tasks()), 1)

    def test_database_rejects_invalid_direct_write(self):
        with sqlite3.connect(self.path) as connection, self.assertRaises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO tasks(title,focus_minutes,break_minutes,sessions) VALUES ('bad',0,5,4)")

    def test_pending_tasks_sort_before_completed(self):
        first = self.store.save('First', 25, 5, 4)
        second = self.store.save('Second', 25, 5, 4)
        self.store.set_completed(second, True)
        self.assertEqual([row['id'] for row in self.store.list_tasks()], [first, second])

    def test_delete_and_undo_preserve_task_details(self):
        task_id = self.store.save('Keep my plan', 30, 7, 3)
        self.store.set_completed(task_id, True)
        self.store.delete(task_id)
        reopened = TaskStore(self.path)
        self.assertIsNone(reopened.get(task_id))
        self.assertEqual(reopened.list_tasks(), [])
        with self.assertRaises(ValueError):
            reopened.save('No edit after delete', 25, 5, 4, task_id)
        reopened.restore(task_id)
        task = reopened.get(task_id)
        self.assertEqual((task['title'], task['focus_minutes'], task['break_minutes'], task['sessions'], task['completed']), ('Keep my plan', 30, 7, 3, 1))

    def test_existing_database_is_migrated_without_losing_tasks(self):
        legacy_path = Path(self.directory.name) / 'legacy.sqlite3'
        with sqlite3.connect(legacy_path) as connection:
            connection.execute('CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT, focus_minutes INTEGER, break_minutes INTEGER, sessions INTEGER, completed INTEGER, created_at TEXT)')
            connection.execute("INSERT INTO tasks VALUES (1, 'Existing task', 25, 5, 4, 0, '2026-10-16 21:30:00')")
        migrated = TaskStore(legacy_path)
        self.assertEqual(migrated.get(1)['title'], 'Existing task')
        migrated.delete(1)
        self.assertEqual(migrated.list_tasks(), [])
        migrated.restore(1)
        self.assertEqual(migrated.get(1)['created_at'], '2026-10-16 21:30:00')

    def test_failed_migration_rolls_back_and_keeps_backup(self):
        legacy = Path(self.directory.name) / 'rollback.sqlite3'
        with sqlite3.connect(legacy) as connection:
            connection.execute('CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT, focus_minutes INTEGER, break_minutes INTEGER, sessions INTEGER, completed INTEGER, created_at TEXT)')
            connection.execute("INSERT INTO tasks VALUES (1, 'Preserve', 25, 5, 4, 0, '2026-10-16 21:30:00')")
        original_connect = sqlite3.connect
        class BrokenConnection(sqlite3.Connection):
            def execute(self, statement, *args):
                if 'CREATE TABLE IF NOT EXISTS focus_sessions' in statement:
                    raise sqlite3.OperationalError('simulated migration failure')
                return super().execute(statement, *args)
        with patch('task_store.sqlite3.connect', side_effect=lambda *args, **kwargs: original_connect(*args, factory=BrokenConnection, **kwargs)):
            with self.assertRaises(sqlite3.OperationalError):
                TaskStore(legacy)
        with original_connect(legacy) as connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 0)
            self.assertNotIn('planned_date', [row[1] for row in connection.execute('PRAGMA table_info(tasks)')])
            self.assertEqual(connection.execute('SELECT title FROM tasks').fetchone()[0], 'Preserve')
        self.assertTrue(legacy.with_suffix('.pre-v1.bak').exists())
        self.assertEqual(TaskStore(legacy).get(1)['title'], 'Preserve')


class DateGroupingTests(unittest.TestCase):
    def test_utc_timestamps_use_local_calendar_day(self):
        tasks = [dict(id=1, completed=0, created_at='2026-10-16 21:30:00'),
                 dict(id=2, completed=0, created_at='2026-10-16 20:30:00')]
        groups = group_tasks_by_date(tasks, timezone(timedelta(hours=3)))
        self.assertEqual([day for day, _ in groups], [date(2026, 10, 17), date(2026, 10, 16)])
        self.assertEqual(groups[0][1][0]['id'], 1)

    def test_today_expands_and_past_collapses_and_choice_survives_refresh(self):
        row = dict(id=1, title='Today task', completed=0, focus_minutes=25, break_minutes=5, sessions=4,
                   created_at=datetime.now(timezone.utc).isoformat())
        old_row = dict(row, id=2, created_at='2020-01-01 12:00:00')
        store = Mock()
        store.list_tasks.return_value = [old_row, row]
        view = TaskList(FakePage(), store, Mock())
        view.refresh()
        self.assertEqual(view.rows.controls[0].title.value, 'Today')
        self.assertTrue(view.rows.controls[0].initially_expanded)
        self.assertFalse(view.rows.controls[1].initially_expanded)
        view.rows.controls[0].on_change(SimpleNamespace(data='false'))
        view.refresh()
        self.assertFalse(view.rows.controls[0].initially_expanded)

    def test_delete_shows_undo_and_restores_the_task(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / 'tasks.sqlite3')
            task_id = store.save('Undo me', 25, 5, 4)
            page = FakePage()
            view = TaskList(page, store, Mock())
            view.delete(task_id)
            self.assertEqual(store.list_tasks(), [])
            self.assertEqual(page.dialogs[-1].action, 'Undo')
            page.dialogs[-1].on_action(None)
            self.assertIsNotNone(store.get(task_id))

    def test_invalid_legacy_date_has_a_collapsed_fallback(self):
        groups = group_tasks_by_date([dict(id=1, completed=0, created_at='invalid')])
        self.assertIsNone(groups[0][0])


class FakePage:
    def __init__(self):
        self.window = SimpleNamespace(center=lambda: None)
        self.overlay = []
        self.dialogs = []
    def update(self): pass
    def add(self, control): pass
    def open(self, dialog): self.dialogs.append(dialog)
    def close(self, dialog): pass


class TaskTimerTests(unittest.TestCase):
    def test_task_plan_completion_and_early_stop(self):
        from timer_controller import TimerController
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / 'tasks.sqlite3')
            completed_id = store.save('Practice SQL', 2, 0, 2)
            cancelled_id = store.save('Read later', 30, 5, 4)
            now = [0.0]
            timer = TimerController(store, clock=lambda: now[0])
            timer.start('Read later', 30, 5, 4, cancelled_id)
            self.assertEqual(timer.state['remaining'], 1800)
            timer.stop()
            self.assertEqual(store.get(cancelled_id)['completed'], 0)
            timer.start('Practice SQL', 2, 0, 2, completed_id)
            for _ in range(48):
                now[0] += 5
                timer.tick()
            self.assertIsNone(timer.state)
            self.assertEqual(TaskStore(store.path).get(completed_id)['completed'], 1)
            self.assertEqual(store.get(cancelled_id)['completed'], 0)


if __name__ == '__main__':
    unittest.main()
