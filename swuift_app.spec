# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the SWUIFT Desktop Application.
#
# Build commands
# --------------
# macOS ARM64 (Apple Silicon):
#   arch -arm64 pyinstaller swuift_app.spec
#
# macOS x86_64 (Intel or Rosetta):
#   arch -x86_64 pyinstaller swuift_app.spec
#
# Windows x86_64 or ARM64:
#   pyinstaller swuift_app.spec
#
# Output: dist/SWUIFT.app (macOS) or dist/SWUIFT/ (Windows)

import sys
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Collect imageio_ffmpeg's bundled ffmpeg binary so the frozen app can find it.
_imageio_ffmpeg_datas = collect_data_files("imageio_ffmpeg", includes=["*.exe", "ffmpeg*"])

# Icon paths (relative to this spec file)
ICON_MACOS = "SWUIFT.icns"
ICON_WIN   = "SWUIFT.ico"
ICON       = ICON_MACOS if sys.platform == "darwin" else ICON_WIN

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    ["swuift_app.py"],
    pathex=["."],
    binaries=[],
    datas=[
        # Bundle the icon so runtime QIcon() can find it
        ("SWUIFT.icns", "."),
        ("SWUIFT.ico",  "."),
        # Bundle the swuift source package
        ("swuift", "swuift"),
        # GUI package
        ("gui", "gui"),
        # imageio_ffmpeg bundled ffmpeg binary
        *_imageio_ffmpeg_datas,
    ],
    hiddenimports=[
        # NumPy / SciPy
        "numpy",
        "numpy.core._multiarray_umath",
        "numpy.core._methods",
        "scipy",
        "scipy.io",
        "scipy.io.matlab",
        # HDF5
        "h5py",
        "h5py._hl",
        "h5py._hl.files",
        # Matplotlib
        "matplotlib",
        "matplotlib.backends.backend_agg",
        # imageio
        "imageio",
        "imageio_ffmpeg",
        # tqdm
        "tqdm",
        "tqdm.auto",
        # av (PyAV)
        "av",
        # PySide6
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        # Pillow
        "PIL",
        "PIL.Image",
    ],
    excludes=[
        "tkinter",
        "PyQt5",
        "PyQt6",
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---------------------------------------------------------------------------
# EXE / onedir build
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SWUIFT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No console window
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SWUIFT",
)

# ---------------------------------------------------------------------------
# macOS .app bundle
# ---------------------------------------------------------------------------
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="SWUIFT.app",
        icon=ICON_MACOS,
        bundle_identifier="com.swuift.app",
        info_plist={
            "CFBundleName": "SWUIFT",
            "CFBundleDisplayName": "SWUIFT",
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,  # Supports dark mode
            "LSMinimumSystemVersion": "11.0",
        },
    )
