from __future__ import annotations

import ast
import struct
import tomllib
from pathlib import Path

from scripts.create_icon import OUTPUT
from scripts.write_build_info import write_build_info
from statguard_desktop.resources import resource_path

ROOT = Path(__file__).resolve().parents[1]


def test_icon_is_original_multisize_ico_with_source_asset() -> None:
    icon = OUTPUT.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", icon)
    sizes = [
        struct.unpack_from("<BBBBHHII", icon, 6 + index * 16)[0] or 256 for index in range(count)
    ]
    assert (reserved, kind, count) == (0, 1, 4)
    assert sizes == [16, 32, 48, 256]
    assert (ROOT / "assets" / "statguard-desktop.svg").is_file()
    package_icon = ROOT / "src" / "statguard_desktop" / "assets" / "statguard-desktop.ico"
    assert package_icon.read_bytes() == icon


def test_resource_path_supports_source_and_frozen_roots(monkeypatch, tmp_path) -> None:
    import sys

    source = resource_path("assets/statguard-desktop.ico")
    assert source.is_file()
    assert source.read_bytes() == (ROOT / "assets" / "statguard-desktop.ico").read_bytes()
    package_source = ROOT / "src" / "statguard_desktop" / "assets" / "statguard-desktop.ico"
    assert package_source.read_bytes() == source.read_bytes()
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resource_path("assets/icon.ico") == tmp_path / "assets" / "icon.ico"


def test_build_info_is_minimal_and_records_executable_hash(tmp_path) -> None:
    import hashlib

    executable = tmp_path / "StatGuardDesktop.exe"
    executable.write_bytes(b"test-executable")
    destination = tmp_path / "build-info.json"
    payload = write_build_info(executable, destination)
    assert set(payload) == {
        "desktop_version",
        "statguard_version",
        "python_version",
        "pyside6_version",
        "pyinstaller_version",
        "platform",
        "architecture",
        "executable_sha256",
    }
    assert payload["desktop_version"] == "0.1.0"
    assert payload["statguard_version"] == "1.0.0"
    assert payload["executable_sha256"] == hashlib.sha256(b"test-executable").hexdigest()
    encoded = destination.read_text(encoding="utf-8")
    assert str(tmp_path) not in encoded
    assert "USERNAME" not in encoded and "COMPUTERNAME" not in encoded
    assert (
        (tmp_path / "StatGuardDesktop.exe.sha256")
        .read_text(encoding="ascii")
        .startswith(payload["executable_sha256"])
    )


def test_windows_version_resource_and_dependency_policy() -> None:
    metadata = (ROOT / "packaging" / "version_info.txt").read_text(encoding="utf-8")
    for expected in (
        "0, 1, 0, 0",
        "StatGuard Desktop",
        "StatGuardDesktop",
        "StatGuardDesktop.exe",
        "StatGuard contributors",
    ):
        assert expected in metadata
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["version"] == "0.1.0"
    assert project["requires-python"] == ">=3.11,<3.14"
    assert "Development Status :: 3 - Alpha" in project["classifiers"]
    assert "Programming Language :: Python :: 3.11" in project["classifiers"]
    assert "Programming Language :: Python :: 3.12" in project["classifiers"]
    assert "Programming Language :: Python :: 3.13" in project["classifiers"]
    assert any(dep.startswith("PySide6>=6.8.3,<6.9") for dep in project["dependencies"])
    assert any("statguard-1.0.0-py3-none-any.whl" in dep for dep in project["dependencies"])


def test_runtime_sources_do_not_import_network_clients() -> None:
    forbidden = {"requests", "urllib", "socket", "httpx", "aiohttp"}
    for source in (ROOT / "src" / "statguard_desktop").glob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = {alias.name.split(".", 1)[0] for alias in node.names}
                assert imported.isdisjoint(forbidden), source.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".", 1)[0] not in forbidden, source.name


def test_portable_script_packages_only_user_facing_files() -> None:
    script = (ROOT / "scripts" / "package_portable_windows.ps1").read_text(encoding="utf-8")
    assert "StatGuardDesktop.exe" in script
    assert "README.txt" in script and "LICENSE.txt" in script and "SHA256SUMS.txt" in script
    assert "OpenRead" in script and "enabled_rule_ids" in script
    assert "--report-smoke" in script
    assert "Get-FileHash -Algorithm SHA256" in script
