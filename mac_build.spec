# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['apple_music_play_history_converter.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['tkinter', 'tkinter.ttk', 'sv_ttk', '_tkinter', 'Tkinter'],
    hookspath=['.'],  # Look for hooks in the current directory
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
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
    icon=['images/aphc.icns'],
)
app = BUNDLE(
    exe,
    name='Apple Music History Converter.app',
    icon='images/aphc.icns',
    bundle_identifier=None,
)
