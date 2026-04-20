"""Top-level launcher for the SWUIFT desktop application.

Usage:
    python swuift_app.py
"""

import multiprocessing
import os
import sys

# Required for PyInstaller frozen apps on Windows/macOS so that
# multiprocessing worker processes don't re-execute the GUI entry point.
multiprocessing.freeze_support()

# Ensure the project root is on the path when running directly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app import run

if __name__ == "__main__":
    run()
