# -*- mode: python ; coding: utf-8 -*-
"""Official MULTI-AI Windows portable application (onedir, no console)."""
from pathlib import Path

project = Path(SPECPATH).resolve()
a = Analysis(
    [str(project / 'main.py')],
    pathex=[str(project)],
    binaries=[],
    datas=[(str(project / 'frontend'), 'frontend'), (str(project / 'assets'), 'assets')],
    hiddenimports=['keyring.backends.Windows'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Multi-AI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(project / 'assets' / 'icon.ico'),
    version=str(project / 'windows-version.txt'),
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False,
    name='MULTI-AI',
)
