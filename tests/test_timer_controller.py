from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from task_store import TaskStore
from timer_controller import TimerController, InstanceLock


class TimerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.temp.name) / 'test.sqlite3')
        self.now = 0.0
        self.wall = datetime(2026, 10, 17, 10, tzinfo=timezone.utc)
        self.events = []
        self.timer = self.controller()

    def tearDown(self):
        self.temp.cleanup()

    def controller(self):
        return TimerController(self.store, clock=lambda: self.now, wall_clock=lambda: self.wall,
            on_event=lambda event, state: self.events.append(event))

    def advance(self, seconds, timer=None):
        timer = timer or self.timer
        while seconds > 0:
            step = min(seconds, 5)
            self.now += step
            self.wall += timedelta(seconds=step)
            timer.tick()
            seconds -= step

    def test_focus_pause_close_recovery_does_not_count_offline_time(self):
        self.timer.start('Math', 1, 1, 2)
        self.advance(17)
        self.timer.suspend()
        self.assertAlmostEqual(self.store.active()['remaining'], 43)
        self.now += 3600
        self.wall += timedelta(hours=1)
        recovered = self.controller()
        self.assertTrue(recovered.recover())
        self.assertTrue(recovered.state['paused'])
        self.advance(30, recovered)
        self.assertEqual(recovered.state['remaining'], 43)
        recovered.resume()
        self.advance(3, recovered)
        recovered.pause()
        self.assertAlmostEqual(self.store.history()[0]['focus_seconds'], 20)
        self.assertEqual(len(self.store.history()), 1)

    def test_crash_loses_at_most_checkpoint_window(self):
        self.timer.start('Math', 1, 0, 1)
        self.advance(7)
        recovered = self.controller()
        recovered.recover()
        self.assertEqual(recovered.state['remaining'], 55)
        self.assertEqual(self.store.history()[0]['focus_seconds'], 5)

    def test_break_recovery_and_final_break_toggle(self):
        self.timer.start('Math', 1, 1, 1, final_break=True)
        self.advance(60)
        self.assertEqual(self.timer.state['phase'], 'break')
        self.advance(7)
        self.timer.suspend()
        recovered = self.controller()
        recovered.recover()
        self.assertEqual(recovered.state['phase'], 'break')
        self.assertEqual(recovered.state['remaining'], 53)
        recovered.resume()
        recovered.skip()
        self.assertIsNone(recovered.state)
        self.assertEqual(self.store.history()[0]['status'], 'completed')
        self.timer.state = None  # Simulate replacing the previous process/controller.
        self.timer.start('No final break', 1, 5, 1, final_break=False)
        self.advance(60)
        self.assertIsNone(self.timer.state)

    def test_skip_focus_keeps_partial_time_without_completing_task(self):
        task_id = self.store.save('Task', 1, 1, 2)
        self.timer.start('Task', 1, 1, 2, task_id, False)
        self.advance(12)
        self.timer.skip()
        self.assertEqual((self.timer.state['phase'], self.timer.state['session_index']), ('focus', 2))
        self.advance(60)
        self.assertEqual(self.store.get(task_id)['completed'], 0)
        history = self.store.history()[0]
        self.assertEqual(history['completed_sessions'], 1)
        self.assertEqual(history['focus_seconds'], 72)
        self.assertEqual(history['status'], 'skipped')

    def test_stop_retains_partial_focus(self):
        self.timer.start('Partial', 1, 0, 1)
        self.advance(13)
        self.timer.stop()
        self.assertIsNone(self.store.active())
        self.assertEqual(self.store.history()[0]['focus_seconds'], 13)
        self.assertEqual(self.store.history()[0]['completed_sessions'], 0)

    def test_sleep_pauses_without_credit(self):
        self.timer.start('Sleep', 1, 0, 1)
        self.advance(5)
        self.now += 600
        self.timer.tick()
        self.assertTrue(self.timer.state['paused'])
        self.assertEqual(self.timer.state['remaining'], 55)
        self.assertEqual(self.store.history()[0]['focus_seconds'], 5)

    def test_sleep_detected_when_monotonic_clock_excludes_sleep(self):
        self.timer.start('Sleep', 1, 0, 1)
        self.advance(5)
        self.wall += timedelta(hours=1)
        self.now += .2
        self.timer.tick()
        self.assertTrue(self.timer.state['paused'])
        self.assertEqual(self.timer.state['remaining'], 55)

    def test_checkpoint_retries_do_not_double_count_intervals(self):
        self.timer.start('Retry', 1, 0, 1)
        state = self.timer.snapshot()
        interval = ('same-id', state['run_id'], 1, self.wall.isoformat(), (self.wall + timedelta(seconds=5)).isoformat(), 5)
        self.store.checkpoint(state, [interval])
        self.store.checkpoint(state, [interval])
        self.assertEqual(self.store.history()[0]['focus_seconds'], 5)

    def test_invalid_checkpoint_can_be_discarded_without_losing_history(self):
        self.timer.start('Preserve history', 1, 0, 1)
        self.advance(5)
        with self.store._connect() as connection:
            connection.execute("UPDATE active_timer SET state='not-json'")
        with self.assertRaises(ValueError):
            self.controller().recover()
        self.store.discard_invalid_checkpoint()
        self.assertIsNone(self.store.active())
        self.assertEqual(self.store.history()[0]['focus_seconds'], 5)
        self.assertEqual(self.store.history()[0]['status'], 'interrupted')

    def test_task_date_does_not_shift_with_timezone(self):
        from TaskList import group_tasks_by_date
        task_id = self.store.save('Scheduled', 25, 5, 4, planned_date='2026-10-20')
        row = self.store.get(task_id)
        self.assertEqual(group_tasks_by_date([row], timezone(timedelta(hours=-12)))[0][0], date(2026,10,20))

    def test_deleted_task_can_recover_without_being_restored(self):
        task_id = self.store.save('Deleted', 1, 0, 1)
        self.timer.start('Deleted', 1, 0, 1, task_id)
        self.timer.suspend()
        self.store.delete(task_id)
        recovered = self.controller()
        recovered.recover()
        recovered.resume()
        self.advance(60, recovered)
        self.assertIsNone(self.store.get(task_id))
        self.assertEqual(self.store.history()[0]['completed_sessions'], 1)

    def test_transition_failure_can_retry_without_losing_session(self):
        self.timer.start('Retry', 1, 1, 1)
        self.advance(55)
        self.now += 5
        with patch.object(self.store, 'checkpoint', side_effect=sqlite3.OperationalError('locked')):
            with self.assertRaises(sqlite3.OperationalError):
                self.timer.tick()
        self.assertEqual(self.timer.state['phase'], 'focus')
        self.timer.tick()
        self.assertEqual(self.timer.state['phase'], 'break')
        self.assertEqual(self.store.history()[0]['completed_sessions'], 1)
        self.assertEqual(self.store.history()[0]['focus_seconds'], 60)

    def test_second_instance_is_rejected(self):
        owner = InstanceLock(self.store.path)
        try:
            with self.assertRaises(ValueError):
                InstanceLock(self.store.path)
        finally:
            owner.close()
        next_owner = InstanceLock(self.store.path)
        next_owner.close()

    def test_stats_split_midnight_and_exclude_pauses(self):
        self.wall = datetime(2026, 10, 16, 20, 59, 50, tzinfo=timezone.utc)
        self.timer.start('Midnight', 1, 0, 1)
        self.advance(20)
        self.timer.pause()
        self.advance(60)
        stats = self.store.daily_stats(today=date(2026,10,17), local_timezone=timezone(timedelta(hours=3)))
        self.assertAlmostEqual(stats['2026-10-16']['focus_seconds'], 10)
        self.assertAlmostEqual(stats['2026-10-17']['focus_seconds'], 10)
        history = self.store.history_for_day('2026-10-17', timezone(timedelta(hours=3)))
        self.assertEqual(len(history), 1)
        self.assertAlmostEqual(history[0]['focus_seconds'], 10)

    def test_stats_handle_daylight_saving_boundary(self):
        self.timer.start('DST', 1, 0, 1)
        state = self.timer.snapshot()
        self.store.checkpoint(state, [('dst',state['run_id'],1,'2026-11-01T04:00:00+00:00','2026-11-02T05:00:00+00:00',90000)])
        stats = self.store.daily_stats(today=date(2026,11,2), local_timezone=ZoneInfo('America/New_York'))
        self.assertEqual(stats['2026-11-01']['focus_seconds'], 90000)

    def test_completion_reversal_and_duplicate_checkpoints(self):
        task_id = self.store.save('Done', 1, 0, 1)
        self.timer.start('Done', 1, 0, 1, task_id)
        self.advance(60)
        self.assertTrue(self.store.get(task_id)['completed'])
        self.store.set_completed(task_id, True)
        self.assertEqual(self.store.daily_stats(today=date.today())[date.today().isoformat()]['tasks'], 1)
        self.store.set_completed(task_id, False)
        self.assertEqual(self.store.daily_stats()[date.today().isoformat()]['tasks'], 0)

    def test_plans_priority_unicode_and_literal_search(self):
        low = self.store.save('Straße 100%', 25, 5, 4, planned_date='2026-11-01', priority=0, final_break=False)
        high = self.store.save('تعلم الألمانية', 30, 5, 3, planned_date='2026-11-01', priority=2)
        self.assertEqual(self.store.list_tasks(planned_date='2026-11-01')[0]['id'], high)
        self.assertEqual(self.store.list_tasks(search='STRASSE')[0]['id'], low)
        self.assertEqual(len(self.store.list_tasks(search='%')), 1)
        self.assertEqual(self.store.list_tasks(search='الألمانية')[0]['id'], high)
        self.assertFalse(self.store.get(low)['final_break'])
        with self.assertRaises(ValueError):
            self.store.save('Bad date',25,5,4,planned_date='2026-02-30')


if __name__ == '__main__':
    unittest.main()
