"""Select the branded macOS renderer shipped inside a frozen FocusNest build."""

import hashlib
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile

from branding import APP_NAME, VERSION


def prepare_desktop_runtime():
    if not getattr(sys, 'frozen', False) or sys.platform != 'darwin':
        return
    from flet_desktop import get_package_bin_dir
    from flet.utils import safe_tar_extractall
    from task_store import default_database_path

    archive = Path(get_package_bin_dir()) / 'flet-macos.tar.gz'
    if not archive.is_file():
        raise RuntimeError('The FocusNest desktop renderer is missing. Rebuild the application.')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()[:16]
    parent = default_database_path().parent / 'FocusNest-runtime'
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / f'{VERSION}-{digest}'
    expected = target / f'{APP_NAME}.app'
    if not expected.is_dir():
        temporary = Path(tempfile.mkdtemp(prefix='extract-', dir=parent))
        try:
            with tarfile.open(archive, 'r:gz') as source:
                safe_tar_extractall(source, str(temporary))
            if not (temporary / f'{APP_NAME}.app').is_dir():
                raise RuntimeError('The bundled desktop renderer has the wrong application identity.')
            try:
                temporary.rename(target)
            except OSError:
                if not expected.is_dir():
                    raise
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    # Avoid reusing the generic Flet.app cache from older development versions.
    os.environ['FLET_VIEW_PATH'] = str(target)
