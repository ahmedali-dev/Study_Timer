"""Bundle the app-specific native renderer rather than a global Flet cache."""

import os
from flet_desktop import get_package_bin_dir

datas = [(os.environ.get('FOCUSNEST_RUNTIME_DIR') or get_package_bin_dir(), 'flet_desktop/app')]
