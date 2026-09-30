# PyInstaller one-file Windows desktop executable.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

project_root = Path(SPECPATH).resolve().parent
hiddenimports = collect_submodules("statguard.rules")

a = Analysis(
    [str(project_root / "src" / "statguard_desktop" / "__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=copy_metadata("statguard"),
    hiddenimports=hiddenimports,
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
    name="StatGuardDesktop",
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
)
