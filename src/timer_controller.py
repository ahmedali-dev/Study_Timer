"""Recoverable timer state machine; the UI only drives and displays this state."""

import copy
from datetime import datetime, timedelta, timezone
import math
import threading
import time
import uuid


class TimerController:
    def __init__(self, store, on_change=None, on_event=None, clock=time.monotonic, wall_clock=None):
        self.store = store
        self.on_change = on_change or (lambda: None)
        self.on_event = on_event or (lambda event, state: None)
        self.clock = clock
        self.wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))
        self.lock = threading.RLock()
        self.state = None
        self.pending = []
        self.last_tick = self.last_save = clock()
        self.last_wall = self.wall_clock()

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.state)

    def recover(self):
        with self.lock:
            state = self.store.active()
            if state is None:
                return False
            required = ('run_id', 'title', 'task_id', 'phase', 'session_index', 'remaining', 'focus_minutes', 'break_minutes', 'sessions', 'final_break', 'skipped', 'started_at')
            if any(key not in state for key in required) or state['phase'] not in ('focus', 'break'):
                raise ValueError('The saved timer cannot be recovered. Your tasks and history are unaffected.')
            if not (state['focus_minutes'] > 0 and state['break_minutes'] >= 0 and state['sessions'] > 0
                    and 1 <= state['session_index'] <= state['sessions'] and math.isfinite(state['remaining']) and state['remaining'] >= 0):
                raise ValueError('The saved timer contains invalid values.')
            state['paused'] = True
            self.state = state
            self.last_tick = self.last_save = self.clock()
            self.last_wall = self.wall_clock()
            self._save()
            return True

    def start(self, title, focus_minutes, break_minutes, sessions, task_id=None, final_break=True):
        with self.lock:
            if self.state is not None:
                raise ValueError('Finish or discard the current timer first.')
            if focus_minutes <= 0 or break_minutes < 0 or sessions <= 0:
                raise ValueError('Focus time and sessions must be positive; break time may be zero.')
            state = dict(run_id=uuid.uuid4().hex, title=title, task_id=task_id,
                focus_minutes=focus_minutes, break_minutes=break_minutes, sessions=sessions,
                final_break=bool(final_break), phase='focus', session_index=1,
                remaining=float(focus_minutes * 60), paused=False, skipped=False,
                started_at=self.wall_clock().isoformat())
            self.store.create_run(state)
            self.state = state
            self.last_tick = self.last_save = self.clock()
            self.last_wall = self.wall_clock()
            self.pending = []
            self.on_event('focus', copy.deepcopy(state))
            self.on_change()

    def _save(self, session_result=None, outcome=None):
        self.store.checkpoint(self.state, self.pending, session_result, outcome)
        self.pending.clear()
        self.last_save = self.clock()

    def tick(self):
        with self.lock:
            if self.state is None:
                return
            now = self.clock()
            elapsed = max(0, now - self.last_tick)
            self.last_tick = now
            wall = self.wall_clock()
            wall_elapsed = (wall - self.last_wall).total_seconds()
            self.last_wall = wall
            if elapsed > 10 or wall_elapsed > 10:
                # Do not count sleep or a long system stall as observed focus.
                self.state['paused'] = True
                self._save()
                self.on_event('suspended', copy.deepcopy(self.state))
            elif not self.state['paused']:
                credited = min(elapsed, self.state['remaining'])
                if credited > 0 and self.state['phase'] == 'focus':
                    end = wall
                    if self.pending:
                        previous = self.pending[-1]
                        self.pending[-1] = (*previous[:4], end.isoformat(), previous[5] + credited)
                    else:
                        self.pending.append((uuid.uuid4().hex, self.state['run_id'], self.state['session_index'],
                            (end - timedelta(seconds=credited)).isoformat(), end.isoformat(), credited))
                self.state['remaining'] = max(0.0, self.state['remaining'] - credited)
                if self.state['remaining'] <= 0:
                    self._advance()
                elif now - self.last_save >= 5:
                    self._save()
            self.on_change()

    def _advance(self, skipped=False):
        original = copy.deepcopy(self.state)
        try:
            self._advance_unchecked(skipped)
        except Exception:
            self.state = original
            raise

    def _advance_unchecked(self, skipped=False):
        state = self.state
        result = None
        if state['phase'] == 'focus':
            result = (state['run_id'], state['session_index'], 'skipped' if skipped else 'completed', self.wall_clock().isoformat())
            state['skipped'] = state['skipped'] or skipped
            take_break = not skipped and state['break_minutes'] > 0 and (state['session_index'] < state['sessions'] or state['final_break'])
            if take_break:
                state['phase'], state['remaining'] = 'break', float(state['break_minutes'] * 60)
            elif state['session_index'] < state['sessions']:
                state['session_index'] += 1
                state['remaining'] = float(state['focus_minutes'] * 60)
            else:
                self._finish('skipped' if state['skipped'] else 'completed', result)
                return
        elif state['session_index'] < state['sessions']:
            state['phase'] = 'focus'
            state['session_index'] += 1
            state['remaining'] = float(state['focus_minutes'] * 60)
        else:
            self._finish('skipped' if state['skipped'] else 'completed')
            return
        self._save(session_result=result)
        self.on_event(state['phase'], copy.deepcopy(state))

    def pause(self):
        with self.lock:
            self.tick()
            if self.state:
                self.state['paused'] = True
                self._save()
                self.on_change()

    def resume(self):
        with self.lock:
            if self.state:
                self.state['paused'] = False
                self.last_tick = self.clock()
                self.last_wall = self.wall_clock()
                self._save()
                self.on_event('resume', copy.deepcopy(self.state))
                self.on_change()

    def skip(self):
        with self.lock:
            if self.state:
                old_phase = (self.state['phase'], self.state['session_index'])
                self.tick()
                if self.state and (self.state['phase'], self.state['session_index']) == old_phase:
                    self._advance(skipped=self.state['phase'] == 'focus')
                self.last_tick = self.clock()
                self.on_change()

    def stop(self):
        with self.lock:
            self.tick()
            if self.state:
                result = None
                if self.state['phase'] == 'focus':
                    result = (self.state['run_id'], self.state['session_index'], 'partial', self.wall_clock().isoformat())
                self._finish('interrupted', result)
                self.on_change()

    def _finish(self, outcome, session_result=None):
        state = copy.deepcopy(self.state)
        self._save(session_result=session_result, outcome=outcome)
        self.state = None
        self.on_event(outcome, state)

    def suspend(self):
        with self.lock:
            self.pause()


class InstanceLock:
    """An OS lock released automatically after a crash; no stale lock-file issue."""
    def __init__(self, database_path):
        self.file = open(str(database_path) + '.lock', 'a+b')
        try:
            if __import__('sys').platform == 'win32':
                import msvcrt
                self.file.seek(0)
                self.file.write(b'0')
                self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise ValueError('FocusNest is already open for this database.') from None

    def close(self):
        if not self.file.closed:
            self.file.close()
