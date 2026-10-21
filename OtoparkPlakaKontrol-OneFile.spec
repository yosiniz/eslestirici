# -*- mode: python ; coding: utf-8 -*-

import os


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('portable.mode', '.'), ('assets/app_icon.png', 'assets')],
    hiddenimports=['xlrd'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Qt'nin kendi ICU kitaplıkları kullanılmalı; PATH'ten gelen uyumsuz kopyaları alma.
_incompatible_icu_files = {"icuuc.dll", "icudt78.dll"}
a.binaries = [
    item
    for item in a.binaries
    if os.path.basename(item[0]).lower() not in _incompatible_icu_files
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='OtoparkPlakaKontrol-v2.1-Windows-x64',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app_icon.ico',
)
