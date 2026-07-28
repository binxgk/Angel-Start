# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['quicklauncher.py'],
    pathex=['D:/Desktop/工作日志/Tai/快捷启动器源码/.pylibs'],
    binaries=[],
    datas=[('_arrows', '_arrows'), ('data', 'data'), ('app.ico', '.')],
    hiddenimports=['theme'],
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
    a.binaries,
    a.datas,
    [],
    name='快捷启动器',
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
    icon=['app.ico'],
)
