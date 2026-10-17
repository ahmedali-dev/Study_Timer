import os
import sys
import threading
import unittest
from types import ModuleType
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from notifications import DesktopNotifications, MAC_NOTIFICATION_SCRIPT


class NotificationTests(unittest.TestCase):
    def test_macos_text_is_passed_as_data(self):
        title, body = 'A "quoted" title', 'Line one\n$(touch /tmp/never)'
        with patch('notifications.sys.platform', 'darwin'), patch('notifications.subprocess.run') as run:
            DesktopNotifications()._deliver(title, body)
        args, kwargs = run.call_args
        self.assertEqual(args[0], ['/usr/bin/osascript', '-e', MAC_NOTIFICATION_SCRIPT, title, body])
        self.assertNotIn('shell', kwargs)
        self.assertEqual(kwargs['timeout'], 10)

    def test_linux_uses_notify_send(self):
        with patch('notifications.sys.platform', 'linux'), patch('notifications.shutil.which', return_value='/usr/bin/notify-send'), patch('notifications.subprocess.run') as run:
            DesktopNotifications()._deliver('Focus', 'Start')
        self.assertEqual(run.call_args.args[0][-3:], ['--', 'Focus', 'Start'])

    def test_windows_uses_native_backend(self):
        backend = ModuleType('plyer.platforms.win.libs.balloontip')
        backend.balloon_tip = Mock()
        with patch('notifications.sys.platform', 'win32'), patch.dict(sys.modules, {'plyer.platforms.win.libs.balloontip': backend}), patch('notifications.os.path.isfile', return_value=True):
            DesktopNotifications('icon.ico')._deliver('Focus', 'Start')
        self.assertEqual(backend.balloon_tip.call_args.kwargs['app_icon'], 'icon.ico')
        self.assertEqual(backend.balloon_tip.call_args.kwargs['app_name'], 'FocusNest')

    def test_missing_linux_tool_reports_failure_without_raising(self):
        callback = Mock()
        with patch('notifications.sys.platform', 'linux'), patch('notifications.shutil.which', return_value=None), self.assertLogs('notifications', level='WARNING'):
            worker = DesktopNotifications().send('Focus', 'Start', callback)
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertFalse(callback.call_args.args[0])

    def test_delivery_failure_is_contained(self):
        callback = Mock()
        with patch.object(DesktopNotifications, '_deliver', side_effect=OSError('denied')), self.assertLogs('notifications', level='WARNING'):
            worker = DesktopNotifications().send('Focus', 'Start', callback)
            worker.join(2)
        self.assertFalse(callback.call_args.args[0])

    def test_delivery_runs_in_background(self):
        started, release = threading.Event(), threading.Event()
        callback = Mock()
        def deliver(*args):
            started.set()
            release.wait(2)
        with patch.object(DesktopNotifications, '_deliver', side_effect=deliver):
            worker = DesktopNotifications().send('Focus', 'Start', callback)
            try:
                self.assertTrue(started.wait(1))
                self.assertTrue(worker.is_alive())
                callback.assert_not_called()
            finally:
                release.set()
                worker.join(2)
        self.assertTrue(callback.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
