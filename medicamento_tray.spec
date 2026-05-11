# -*- mode: python ; coding: utf-8 -*-
# Gera um único .exe sem janela de console. Execute na pasta do projeto:
#   python -m PyInstaller --clean medicamento_tray.spec

a = Analysis(
    ["medicamento_app.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=["winotify"],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="MedicamentoLembretes",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
)
