"""QApplication entry point and application-level constants."""

from __future__ import annotations

import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# Application-level directory constants
# ---------------------------------------------------------------------------

# When running from source, this is the repository root.  When running
# from a PyInstaller bundle, ``sys.argv[0]`` points to the .exe / .app.
APP_DIR: str = os.path.dirname(os.path.abspath(sys.argv[0]))

# The icon lives at the project root alongside this package.
_ICON_PATH: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "SWUIFT.icns")


def run() -> None:
    """Create QApplication, show MainWindow, enter event loop."""
    # Import here to avoid circular imports before QApplication exists.
    from .main_window import MainWindow  # noqa: PLC0415

    app = QApplication(sys.argv)
    app.setApplicationName("SWUIFT")
    app.setOrganizationName("SWUIFT")
    app.setOrganizationDomain("swuift.app")

    if os.path.isfile(_ICON_PATH):
        app.setWindowIcon(QIcon(_ICON_PATH))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
