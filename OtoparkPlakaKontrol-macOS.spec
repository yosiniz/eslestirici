# -*- mode: python ; coding: utf-8 -*-

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

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Otopark Plaka Kontrol',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app_icon.icns',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='Otopark Plaka Kontrol',
)

app = BUNDLE(
    coll,
    name='Otopark Plaka Kontrol.app',
    icon='assets/app_icon.icns',
    bundle_identifier='tr.local.otoparkplakakontrol',
    version='2.1.0',
    info_plist={
        'CFBundleDisplayName': 'Otopark Plaka Kontrol',
        'CFBundleName': 'Otopark Plaka Kontrol',
        'CFBundleShortVersionString': '2.1.0',
        'NSHighResolutionCapable': True,
        'NSHumanReadableCopyright': 'Yerel veri karşılaştırma uygulaması',
    },
)
