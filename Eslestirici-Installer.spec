# -*- mode: python ; coding: utf-8 -*-

"""Windows kurulum paketi için portable işaretçisi içermeyen onedir yapılandırması."""

import os


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/app_icon.png', 'assets')],
    hiddenimports=['xlrd'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Qt kendi ICU kitaplıklarını kullanmalı; PATH'teki uyumsuz kopyalar pakete alınmaz.
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
    [],
    exclude_binaries=True,
    name='Eslestirici',
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

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Eslestirici',
)
