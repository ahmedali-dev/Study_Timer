"""Writable SQLite preferences, with one-time import of legacy JSON settings."""

import json
from pathlib import Path

from task_store import TaskStore


DEFAULTS = dict(study='50', **{'break': '10'}, session='4', bg_music='', final_break=True)


def loadData(store=None):
    store = store or TaskStore()
    saved = store.load_settings()
    if not saved:
        values = dict(DEFAULTS)
        root = Path(__file__).resolve().parent
        for path in (root.parent / 'data' / 'timer_settings.json', root / 'timer_settings.json'):
            if path.exists():
                try:
                    legacy = json.loads(path.read_text())
                    for key in DEFAULTS:
                        if key in legacy:
                            values[key] = legacy[key]
                    break
                except (OSError, ValueError, TypeError):
                    continue
        if not isinstance(values['bg_music'], str) or not Path(values['bg_music']).is_file():
            values['bg_music'] = ''
        store.save_settings(values)
        saved = values
    return {**DEFAULTS, **saved}


def saveData(data, store=None):
    (store or TaskStore()).save_settings(data)
