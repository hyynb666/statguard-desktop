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
    assert {action for action in window._menu_actions} == {
        "open_file",
        "open_folder",
        "clear",
        "exit",
        "search",
        "about",
    }
    assert window._menu_actions["open_file"].shortcut().toString() == "Ctrl+O"
    assert window._menu_actions["open_folder"].shortcut().toString() == "Ctrl+Shift+O"
    assert window._menu_actions["clear"].shortcut().toString() == "Ctrl+L"
    assert window._menu_actions["exit"].shortcut().toString() == "Ctrl+Q"
    assert window._menu_actions["search"].shortcut().toString() == "Ctrl+F"
    assert not window.windowIcon().isNull()
    window.close()


def test_repeated_scans_replace_previous_report(application, tmp_path) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    from tests.helpers import SAFE_ML001

    risky = tmp_path / "first.py"
    safe = tmp_path / "second.py"
    risky.write_text(RISKY_ML001, encoding="utf-8")
    safe.write_text(SAFE_ML001, encoding="utf-8")
    window = MainWindow()

    def run_scan(path: Path) -> None:
        window.path_input.setText(str(path))
        window.start_scan()
        first_thread = window._thread
        window.start_scan()
        assert window._thread is first_thread
        loop = QEventLoop()
        timer = QTimer()
        timer.timeout.connect(lambda: loop.quit() if window._thread is None else None)
        timer.start(20)
        QTimer.singleShot(15000, loop.quit)
        loop.exec()
        timer.stop()
        assert window._thread is None

    run_scan(risky)
    assert "ML001" in {item.rule_id for item in window.last_report.findings}
    run_scan(safe)
    assert window.last_report.results[0].path == str(safe)
    safe_rule_ids = {item.rule_id for item in window.last_report.findings}
    assert "ML001" not in safe_rule_ids
    assert window.findings_model.rowCount() == len(window.last_report.findings)
    run_scan(risky)
    assert window.last_report.results[0].path == str(risky)
    assert window.findings_model.rowCount() == len(window.last_report.findings)
    window.close()


def test_worker_error_message_does_not_leak_exception_text(monkeypatch) -> None:
    from statguard_desktop import workers

    def fail_with_private_detail(*_args):
        raise RuntimeError("private path")

    monkeypatch.setattr(workers, "scan_desktop", fail_with_private_detail)
    worker = workers.ScanWorker("secret/input.py")
    messages = []
    worker.failed.connect(messages.append)
    worker.run()
    assert messages == ["Scan failed unexpectedly."]


def test_gui_recovers_after_worker_failure(application, tmp_path, monkeypatch) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    from statguard_desktop import workers

    source = tmp_path / "input.py"
    source.write_text("pass\n", encoding="utf-8")

    def fail_scan(*_args):
        raise RuntimeError("private project detail")

    monkeypatch.setattr(workers, "scan_desktop", fail_scan)
    window = MainWindow()
    window.path_input.setText(str(source))
    window.start_scan()
    loop = QEventLoop()
    timer = QTimer()
    timer.timeout.connect(lambda: loop.quit() if window._thread is None else None)
    timer.start(20)
    QTimer.singleShot(15000, loop.quit)
    loop.exec()
    timer.stop()
    assert window._thread is None
    assert window.scan_button.isEnabled()
    assert "Scan failed: Scan failed unexpectedly." in window.messages.toPlainText()
    assert "private project detail" not in window.messages.toPlainText()
    window.close()


def test_startup_error_boundary_shows_safe_feedback(application, monkeypatch) -> None:
    from statguard_desktop import __main__ as entry

    messages = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *_args: messages.append(_args[-1]))
    entry._show_startup_error(RuntimeError("secret user directory"))
    assert len(messages) == 1
    assert "unexpected startup error" in messages[0]
    assert "secret user directory" not in messages[0]


def test_startup_error_uses_native_fallback_if_qt_dialog_fails(application, monkeypatch) -> None:
    from statguard_desktop import __main__ as entry

    messages = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("Qt display error")),
    )
    monkeypatch.setattr(entry, "_fallback_startup_error", messages.append)
    entry._show_startup_error(RuntimeError("private startup data"))
    assert messages == ["An unexpected startup error occurred (RuntimeError)."]


def test_main_catches_unexpected_gui_startup_failure(application, monkeypatch) -> None:
    from statguard_desktop import __main__ as entry

    messages = []

    def fail_startup():
        raise RuntimeError("private environment data")

    monkeypatch.setattr(entry, "_run_gui", fail_startup)
    monkeypatch.setattr(QMessageBox, "critical", lambda *_args: messages.append(_args[-1]))
    assert entry.main([]) == 2
    assert len(messages) == 1
    assert "unexpected startup error" in messages[0]
    assert "private environment data" not in messages[0]


def test_broken_python_notebook_and_unsupported_input_keep_window_alive(
    application, tmp_path
) -> None:
    from statguard_desktop.adapter import scan_desktop

    python_file = tmp_path / "broken.py"
    python_file.write_text("def invalid(:\n", encoding="utf-8")
    notebook_file = tmp_path / "broken.ipynb"
    notebook_file.write_text("{broken", encoding="utf-8")
    unsupported = tmp_path / "unsupported.txt"
    unsupported.write_text("text", encoding="utf-8")
    window = MainWindow()
    for path in (python_file, notebook_file, unsupported):
        result = scan_desktop(path)
        window._populate_report(result)
        assert result.report.analysis_errors
        assert window.windowTitle() == "StatGuard Desktop"
        assert "ERROR" in window.messages.toPlainText()
    window.close()


def test_about_dialog_displays_desktop_and_engine_versions(application, monkeypatch) -> None:
    messages = []
    monkeypatch.setattr(QMessageBox, "about", lambda *_args: messages.append(_args[-1]))
    window = MainWindow()
    window._show_about()
    assert "Desktop 0.1.0.dev0" in messages[0]
    assert "Engine StatGuard 1.0.0" in messages[0]
    assert "MIT License" in messages[0]
    assert "github.com/hyynb666/statguard" in messages[0]
    window.close()


def test_empty_project_has_explicit_supported_file_notice(application, tmp_path) -> None:
    from statguard_desktop.adapter import scan_desktop

    result = scan_desktop(tmp_path)
    window = MainWindow()
    window._populate_report(result)
    assert window.empty_state.text() == "No supported .py or .ipynb files found."
    assert "No supported .py or .ipynb files found" in window.messages.toPlainText()
    window.close()


def test_close_waits_for_active_scan_worker(application, tmp_path, monkeypatch, capfd) -> None:
    import time

    from statguard_desktop import workers
    from statguard_desktop.adapter import scan_desktop

    source = tmp_path / "closing.py"
    source.write_text("pass\n", encoding="utf-8")
    original = scan_desktop

    def delayed_scan(*args, **kwargs):
        time.sleep(0.15)
        return original(*args, **kwargs)

    monkeypatch.setattr(workers, "scan_desktop", delayed_scan)
    window = MainWindow()
    window.path_input.setText(str(source))
    window.start_scan()
    thread = window._thread
    assert thread is not None and thread.isRunning()
    window.close()
    assert not thread.isRunning()
    assert "QThread: Destroyed while thread is still running" not in capfd.readouterr().err


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
