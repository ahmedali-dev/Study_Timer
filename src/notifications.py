"""Best-effort desktop notifications without blocking the countdown."""

import logging
import os
import shutil
import subprocess
import sys
import threading
from branding import APP_NAME


logger = logging.getLogger(__name__)
MAC_NOTIFICATION_SCRIPT = """on run argv
    display notification (item 2 of argv) with title (item 1 of argv)
end run
"""


class DesktopNotifications:
    def __init__(self, icon_path=""):
        self.icon_path = icon_path

    def send(self, title, message, on_result=None):
        """Submit off-thread. A successful submission does not guarantee a banner."""
        def worker():
            try:
                self._deliver(title, message)
            except Exception as exc:
                logger.warning("Desktop notification failed: %s", exc)
                result = (False, "Notification unavailable. Check your desktop notification settings and setup.")
            else:
                result = (True, "Notification submitted. If no banner appears, check your system notification settings.")
            if on_result is not None:
                on_result(*result)

        thread = threading.Thread(target=worker, daemon=True, name="desktop-notification")
        thread.start()
        return thread

    def _deliver(self, title, message):
        if sys.platform == "darwin":
            # Pass text as arguments, never interpolate it into executable code.
            subprocess.run(
                ["/usr/bin/osascript", "-e", MAC_NOTIFICATION_SCRIPT, title, message],
                check=True, capture_output=True, timeout=10,
            )
        elif sys.platform == "win32":
            # Run the Windows backend synchronously in our worker so delivery
            # errors are caught here, rather than lost in Plyer's own thread.
            from plyer.platforms.win.libs.balloontip import balloon_tip

            balloon_tip(
                title=title, message=message, app_name=APP_NAME,
                app_icon=self.icon_path if os.path.isfile(self.icon_path) else "",
                timeout=5,
            )
        elif sys.platform.startswith("linux"):
            executable = shutil.which("notify-send")
            if not executable:
                raise RuntimeError("Install notify-send (libnotify-bin on Debian/Ubuntu or libnotify on Fedora/Arch).")
            subprocess.run(
                [executable, f"--app-name={APP_NAME}", "--expire-time=5000", "--", title, message],
                check=True, capture_output=True, timeout=10,
            )
        else:
            raise RuntimeError(f"Notifications are unsupported on {sys.platform}")
