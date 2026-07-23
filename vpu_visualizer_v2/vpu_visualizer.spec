# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for VPU Visualizer 2.0.
# Build with:  pyinstaller vpu_visualizer.spec
# Note: PyInstaller cannot cross-compile; run this on each target OS
# (the GitHub Actions workflow in .github/workflows/build.yml does exactly that).

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('icons', 'icons')],
    hiddenimports=[],
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
    a.datas,
    [],
    name='VPU-Visualizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)

app = BUNDLE(
    exe,
    name='VPU-Visualizer.app',
    icon=None,
    bundle_identifier='com.vpuvisualizer.app',
)
