"""Desktop application entry point and packaged-executable smoke modes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _write_json(path: str | Path, payload: object) -> None:
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="StatGuard Desktop")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--smoke-test", metavar="OUTPUT_JSON", help=argparse.SUPPRESS)
    mode.add_argument("--gui-smoke-test", metavar="OUTPUT_JSON", help=argparse.SUPPRESS)
    mode.add_argument("--engine-info", metavar="OUTPUT_JSON", help=argparse.SUPPRESS)
    mode.add_argument(
        "--scan-smoke", nargs=2, metavar=("INPUT", "OUTPUT_JSON"), help=argparse.SUPPRESS
    )
    mode.add_argument(
        "--report-smoke", nargs=2, metavar=("INPUT", "OUTPUT_DIR"), help=argparse.SUPPRESS
    )
    return parser


def _run_gui(*, smoke_output: str | None = None) -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from statguard_desktop.adapter import scan_metadata
    from statguard_desktop.mainwindow import MainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    window = MainWindow()
    window.show()
    if smoke_output is not None:
        QTimer.singleShot(500, app.quit)
    exit_code = app.exec()
    if smoke_output is not None:
        payload = scan_metadata()
        payload["window_title"] = window.windowTitle()
        payload["scan_button_enabled"] = window.scan_button.isEnabled()
        _write_json(smoke_output, payload)
    return exit_code


def _report_smoke(source: str, output_dir: str) -> None:
    from statguard_desktop.adapter import (
        render_report_html,
        render_report_json,
        render_report_sarif,
        scan_desktop,
    )

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    result = scan_desktop(source)
    for extension, content in (
        ("html", render_report_html(result)),
        ("json", render_report_json(result)),
        ("sarif", render_report_sarif(result)),
    ):
        (target / f"report.{extension}").write_text(content, encoding="utf-8")


def _show_startup_error(error: Exception) -> None:
    """Show a safe GUI error when possible without exposing tracebacks or inputs."""
    if type(error).__name__ == "DesktopIntegrationError":
        message = str(error)
    else:
        message = f"An unexpected startup error occurred ({type(error).__name__})."
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance() or QApplication(sys.argv[:1])
        QMessageBox.critical(None, "StatGuard Desktop could not start.", message)
        del app
    except Exception:
        _fallback_startup_error(message)


def _fallback_startup_error(message: str) -> None:
    """Use the native Windows dialog if Qt itself cannot initialize."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None, message, "StatGuard Desktop could not start.", 0x10
            )
            return
        except Exception:
            pass
    print(f"StatGuard Desktop could not start: {message}", file=sys.stderr)


def _run_scan_smoke(source: str, destination: str) -> int:
    from statguard_desktop.adapter import scan_smoke_payload

    try:
        payload = scan_smoke_payload(source)
        _write_json(destination, payload)
    except Exception as error:
        failure = {
            "application": "StatGuard Desktop",
            "error": type(error).__name__,
            "message": "Scan smoke failed.",
        }
        try:
            _write_json(destination, failure)
        except OSError:
            pass
        raise error
    return 2 if payload["analysis_errors"] else 0


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.smoke_test:
            from statguard_desktop.adapter import scan_metadata

            _write_json(args.smoke_test, scan_metadata())
            return 0
        if args.engine_info:
            from statguard_desktop.adapter import engine_info_payload

            _write_json(args.engine_info, engine_info_payload())
            return 0
        if args.scan_smoke:
            source_path, destination = args.scan_smoke
            return _run_scan_smoke(source_path, destination)
        if args.report_smoke:
            _report_smoke(*args.report_smoke)
            return 0
        if args.gui_smoke_test:
            return _run_gui(smoke_output=args.gui_smoke_test)
        return _run_gui()
    except Exception as error:
        if argv is None or not argv or not any(str(item).startswith("--") for item in argv):
            _show_startup_error(error)
        else:
            print(f"StatGuard Desktop operation failed: {type(error).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
