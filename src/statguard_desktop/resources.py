"""Resolve packaged and source-tree resources from one location."""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative_path: str | Path) -> Path:
    """Return an application resource path for source and PyInstaller builds."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root is not None:
        return Path(frozen_root) / relative_path
    packaged = Path(__file__).resolve().parent / relative_path
    if packaged.exists():
        return packaged
    return Path(__file__).resolve().parents[2] / relative_path
