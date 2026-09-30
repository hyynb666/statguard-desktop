"""Write privacy-minimal metadata for a frozen Windows executable build."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

from PyInstaller import __version__ as pyinstaller_version
from PySide6 import __version__ as pyside6_version

from statguard_desktop import __version__ as desktop_version
from statguard_desktop.adapter import SUPPORTED_CORE_VERSION


def write_build_info(executable: Path, output: Path) -> dict[str, str]:
    """Write versions and executable checksum, omitting machine-specific paths."""
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    info = {
        "desktop_version": desktop_version,
        "statguard_version": SUPPORTED_CORE_VERSION,
        "python_version": platform.python_version(),
        "pyside6_version": pyside6_version,
        "pyinstaller_version": pyinstaller_version,
        "platform": "Windows",
        "architecture": platform.machine(),
        "executable_sha256": digest,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(info, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output.with_name("StatGuardDesktop.exe.sha256").write_text(
        f"{digest}  {executable.name}\n", encoding="ascii"
    )
    return info


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: write_build_info.py EXECUTABLE OUTPUT_JSON")
    write_build_info(Path(sys.argv[1]), Path(sys.argv[2]))
