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
    assert window.custom_config_path.isEnabled() is False
    assert window.browse_config_button.isEnabled() is False
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
    window.rule_filter.setCurrentText("ML001")
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


def test_gui_controls_and_filtering(application, tmp_path) -> None:
    source = tmp_path / "risk.py"
    source.write_text(RISKY_ML001, encoding="utf-8")
    window = MainWindow()
    report = scan_path(source)
    window._populate_report(report)
    assert len(window.rule_checks) == 11
    assert window.enabled_count.text() == "Enabled rules: 11 / 11"
    window.rule_filter.setCurrentText("ML001")
    assert window.proxy_model.rowCount() == 1
    window.search_input.setText("not present")
    assert window.visible_count.text().startswith("Showing 0 of ")
    window._clear_filters()
    window.rule_checks["ML001"].setChecked(False)
    assert window.enabled_count.text() == "Enabled rules: 10 / 11"
    window.close()


def test_config_disabled_rule_can_be_reenabled_in_gui(application, tmp_path) -> None:
    from statguard_desktop.adapter import scan_desktop

    (tmp_path / "pyproject.toml").write_text(
        "[tool.statguard]\ndisable-rules=['ML001']\n", encoding="utf-8"
    )
    source = tmp_path / "risk.py"
    source.write_text(RISKY_ML001, encoding="utf-8")
    window = MainWindow()
    window.path_input.setText(str(source))
    window.config_source.setCurrentText("Project")
    window._load_configuration()
    assert not window.rule_checks["ML001"].isChecked()
    assert "Modified in UI" not in window.config_indicator.text()
    window.rule_checks["ML001"].setChecked(True)
    assert "Modified in UI" in window.config_indicator.text()
    enabled = scan_desktop(source, window._effective_policy())
    assert "ML001" in {finding.rule_id for finding in enabled.report.findings}
    window.rule_checks["ML001"].setChecked(False)
    disabled = scan_desktop(source, window._effective_policy())
    assert "ML001" not in {finding.rule_id for finding in disabled.report.findings}
    window._reset_to_config()
    assert not window.rule_checks["ML001"].isChecked()
    window.close()


def test_invalid_custom_config_is_reported_and_blocks_scan(
    application, tmp_path, monkeypatch
) -> None:
    source = tmp_path / "risk.py"
    source.write_text(RISKY_ML001, encoding="utf-8")
    custom = tmp_path / "bad.toml"
    custom.write_text("[tool.statguard]\nunknown=true\n", encoding="utf-8")
    window = MainWindow()
    window.path_input.setText(str(source))
    window.config_source.setCurrentText("Custom TOML")
    window.custom_config_path.setText(str(custom))
    window._load_configuration()
    assert window._configuration_valid is False
    assert "Invalid StatGuard configuration" in window.config_error.text()
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args))
    window.start_scan()
    assert messages
    assert window.last_result is None
    window.close()


def test_export_json_and_sarif_from_same_result(application, tmp_path, monkeypatch) -> None:
    import json

    from statguard_desktop.adapter import scan_desktop

    source = tmp_path / "risk.py"
    source.write_text(RISKY_ML001, encoding="utf-8")
    result = scan_desktop(source)
    window = MainWindow()
    window.last_result = result
    outputs = iter((tmp_path / "report.json", tmp_path / "report.sarif"))
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args: (str(next(outputs)), ""),
    )
    monkeypatch.setattr(QMessageBox, "critical", lambda *_args: None)
    window._export("json")
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert "ML001" in {item["rule_id"] for item in payload["findings"]}
    window._export("sarif")
    sarif = json.loads((tmp_path / "report.sarif").read_text(encoding="utf-8"))
    assert sarif["version"] == "2.1.0"
    assert "ML001" in {item["ruleId"] for item in sarif["runs"][0]["results"]}
    uri = sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"][
        "uri"
    ]
    assert uri == "risk.py"
    window.close()


def test_threshold_reached_is_visible_without_exiting_gui(application, tmp_path) -> None:
    from statguard_desktop.adapter import make_policy, scan_desktop

    source = tmp_path / "risk.py"
    source.write_text(RISKY_ML001, encoding="utf-8")
    result = scan_desktop(source, make_policy(fail_on="warning"))
    window = MainWindow()
    window._scan_completed(result)
    assert window.threshold_status.text() == "Warning threshold reached"
    assert window.windowTitle() == "StatGuard Desktop"
    assert window.last_result is result
    window.close()
