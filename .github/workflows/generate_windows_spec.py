#!/usr/bin/env python3
"""Generate PyInstaller spec file for Windows builds in GitHub Actions."""

spec_content = '''# -*- mode: python ; coding: utf-8 -*-
# Windows Build Configuration for Apple Music Play History Converter

import os
from PyInstaller.utils.hooks import collect_all, collect_data_files

# Collect all numpy and pandas components
numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all('numpy')
pandas_datas, pandas_binaries, pandas_hiddenimports = collect_all('pandas')

a = Analysis(
    ['..\\\\apple_music_play_history_converter.py'],
    pathex=[],
    binaries=numpy_binaries + pandas_binaries,
    datas=[
        ('..\\\\images\\\\appicon.png', 'images'),
    ] + numpy_datas + pandas_datas,
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'sv_ttk',
        '_tkinter',
        'pandas',
        'pandas._libs',
        'pandas._libs.tslibs',
        'numpy',
        'numpy._core',
        'numpy._core._multiarray_umath',
        'requests',
        'zstandard',
        'duckdb',
        'json',
        'pathlib',
        'threading',
        'queue',
        'urllib.parse',
        'urllib.request',
        'urllib.error',
        'certifi',
        'charset_normalizer',
        'idna',
        'psutil',
        'psutil._psutil_windows',
    ] + numpy_hiddenimports + pandas_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'PIL',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Apple Music History Converter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='..\\\\images\\\\appicon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Apple Music History Converter',
)
'''

with open('build_artifacts/build_windows.spec', 'w') as f:
    f.write(spec_content)

print("Generated build_windows.spec")