from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QPushButton

from statguard_desktop.adapter import scan_path
from statguard_desktop.mainwindow import MainWindow
from tests.helpers import RISKY_ML001


@pytest.fixture(scope="module")
def application():
    instance = QApplication.instance() or QApplication([])
    yield instance


def test_window_initial_state_and_expected_controls(application) -> None:
    window = MainWindow()
    assert window.windowTitle() == "StatGuard Desktop"
    assert window.minimumWidth() >= 900
    assert window.findChild(QPushButton, "browseFileButton").text().startswith("Browse File")
    assert window.findChild(QPushButton, "browseFolderButton").text().startswith("Browse Folder")
    assert window.findChild(QPushButton, "scanButton").text() == "Scan"
    assert window.findChild(QPushButton, "exportHtmlButton").isEnabled() is False
    assert window.findChild(QPushButton, "openHtmlButton").isEnabled() is False
    assert window.findings_model.rowCount() == 0
    assert "statistical correctness" in window.disclaimer.text()
    window._set_scanning(True)
    assert window.findChild(QPushButton, "scanButton").isEnabled() is False
    assert window.findings_view.isEnabled() is False
    window._set_scanning(False)
    assert window.findChild(QPushButton, "scanButton").isEnabled() is True
    window.close()


def test_finding_details_html_export_and_open(application, tmp_path, monkeypatch) -> None:
    source = tmp_path / "risk.py"
    source.write_text(RISKY_ML001, encoding="utf-8")
    window = MainWindow()
    report = scan_path(source)
    window._populate_report(report)
    window.findings_view.selectRow(0)
    assert "ML001" in window.details.toPlainText()
    assert "Risk:" in window.details.toPlainText()

    destination = tmp_path / "report.html"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_args: (str(destination), "HTML"))
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)
    opened: list[object] = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
    window.last_report = report
    window.export_html()
    assert "ML001" in destination.read_text(encoding="utf-8")
    assert window.open_html_button.isEnabled()
    window.open_html()
    assert Path(opened[0].toLocalFile()).resolve() == destination.resolve()
    window.close()
