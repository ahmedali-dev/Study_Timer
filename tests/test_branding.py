import os
from pathlib import Path
import plistlib
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from desktop_runtime import prepare_desktop_runtime
from task_store import default_database_path


class DataCompatibilityTests(unittest.TestCase):
    def test_new_data_override_wins_over_legacy(self):
        with patch.dict(os.environ, {'FOCUSNEST_DATA_DIR': '/new-focusnest', 'STUDY_TIMER_DATA_DIR': '/old-timer'}):
            self.assertEqual(default_database_path(), Path('/new-focusnest') / 'study_timer.sqlite3')

    def test_legacy_data_override_still_works(self):
        with patch.dict(os.environ, {'FOCUSNEST_DATA_DIR': '', 'STUDY_TIMER_DATA_DIR': '/old-timer'}):
            self.assertEqual(default_database_path(), Path('/old-timer') / 'study_timer.sqlite3')

    def test_packaged_storage_folder_is_not_renamed(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'FOCUSNEST_DATA_DIR': '', 'STUDY_TIMER_DATA_DIR': '', 'LOCALAPPDATA': folder}), patch('task_store.sys.frozen', True, create=True), patch('task_store.sys.platform', 'win32'):
            self.assertEqual(default_database_path(), Path(folder) / 'StudyTimer' / 'study_timer.sqlite3')


class BrandedRuntimeTests(unittest.TestCase):
    def test_mac_renderer_extracts_into_own_cache_and_is_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app = root / 'source' / 'FocusNest.app' / 'Contents'
            app.mkdir(parents=True)
            with (app / 'Info.plist').open('wb') as destination:
                plistlib.dump({'CFBundleDisplayName': 'FocusNest'}, destination)
            package = root / 'package'
            package.mkdir()
            with tarfile.open(package / 'flet-macos.tar.gz', 'w:gz') as archive:
                archive.add(app.parent, arcname='FocusNest.app')
            with patch('desktop_runtime.sys.frozen', True, create=True), patch('desktop_runtime.sys.platform', 'darwin'), patch('flet_desktop.get_package_bin_dir', return_value=str(package)), patch.dict(os.environ, {'FOCUSNEST_DATA_DIR': str(root / 'data')}):
                original = os.environ.get('FLET_VIEW_PATH')
                try:
                    prepare_desktop_runtime()
                    target = Path(os.environ['FLET_VIEW_PATH'])
                    self.assertTrue((target / 'FocusNest.app' / 'Contents' / 'Info.plist').is_file())
                    sentinel = target / 'cache-kept'
                    sentinel.touch()
                    prepare_desktop_runtime()
                    self.assertEqual(Path(os.environ['FLET_VIEW_PATH']), target)
                    self.assertTrue(sentinel.exists())
                finally:
                    if original is None:
                        os.environ.pop('FLET_VIEW_PATH', None)
                    else:
                        os.environ['FLET_VIEW_PATH'] = original

    def test_development_run_does_not_change_renderer(self):
        with patch('desktop_runtime.sys.frozen', False, create=True), patch.dict(os.environ, {'FLET_VIEW_PATH': 'existing-development-host'}):
            prepare_desktop_runtime()
            self.assertEqual(os.environ['FLET_VIEW_PATH'], 'existing-development-host')


if __name__ == '__main__':
    unittest.main()
