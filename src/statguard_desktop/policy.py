"""Immutable scan policy and target/config path helpers for the desktop UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CONFIG_PROJECT = "Project"
CONFIG_NONE = "None"
CONFIG_CUSTOM = "Custom TOML"


@dataclass(frozen=True, slots=True)
class DesktopScanPolicy:
    disabled_rules: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    fail_on: str | None = None
    config_source: str = CONFIG_PROJECT
    config_path: str | None = None


def project_config_path(target: str | Path) -> Path:
    path = Path(target)
    return (path if path.is_dir() else path.parent) / "pyproject.toml"


def validate_excludes(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Validate Scanner-compatible exclusions without resolving outside the root."""
    normalized: list[str] = []
    for value in values:
        text = value.strip()
        parts = text.replace("\\", "/").split("/")
        if not text or Path(text).is_absolute() or text.startswith(("/", "\\")):
            raise ValueError("Excluded paths must be nonempty relative paths")
        if (
            any(part in ("", "..") for part in parts)
            or not any(part != "." for part in parts)
            or ":" in parts[0]
        ):
            raise ValueError("Excluded paths must stay inside the scanned directory")
        if text not in normalized:
            normalized.append(text)
    return tuple(normalized)
