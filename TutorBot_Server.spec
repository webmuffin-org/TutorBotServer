# -*- mode: python ; coding: utf-8 -*-

datas = [('static', 'static'),('classes', 'classes'),('.env', '.env')]


a = Analysis(
    ['TutorBot_Server.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['TutorBot_Server', 'pydantic.deprecated.decorator'],
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
    name='TutorBot_Server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
