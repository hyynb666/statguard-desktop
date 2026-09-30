"""Desktop application entry point and packaged-executable smoke modes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from statguard_desktop.adapter import scan_metadata, scan_smoke_payload


def _write_json(path: str | Path, payload: object) -> None:
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="StatGuard Desktop")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--smoke-test", metavar="OUTPUT_JSON", help=argparse.SUPPRESS)
    mode.add_argument("--gui-smoke-test", metavar="OUTPUT_JSON", help=argparse.SUPPRESS)
    mode.add_argument(
        "--scan-smoke", nargs=2, metavar=("INPUT", "OUTPUT_JSON"), help=argparse.SUPPRESS
    )
    args = parser.parse_args(argv)
    if args.smoke_test:
        try:
            _write_json(args.smoke_test, scan_metadata())
        except (OSError, RuntimeError, ValueError) as error:
            print(f"StatGuard Desktop smoke test failed: {type(error).__name__}", file=sys.stderr)
            return 2
        return 0
    if args.scan_smoke:
        source_path, destination = args.scan_smoke
        try:
            payload = scan_smoke_payload(source_path)
            _write_json(destination, payload)
        except (OSError, RuntimeError, ValueError) as error:
            failure = {
                "application": "StatGuard Desktop",
                "error": type(error).__name__,
                "message": str(error),
            }
            try:
                _write_json(destination, failure)
            except OSError:
                pass
            print(f"StatGuard Desktop scan smoke failed: {type(error).__name__}", file=sys.stderr)
            return 2
        return 2 if payload["analysis_errors"] else 0

    if args.gui_smoke_test:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication

        from statguard_desktop.mainwindow import MainWindow

        app = QApplication.instance() or QApplication(sys.argv[:1])
        window = MainWindow()
        window.show()
        QTimer.singleShot(500, app.quit)
        exit_code = app.exec()
        payload = scan_metadata()
        payload["window_title"] = window.windowTitle()
        payload["scan_button_enabled"] = window.scan_button.isEnabled()
        _write_json(args.gui_smoke_test, payload)
        return exit_code

    from PySide6.QtWidgets import QApplication

    from statguard_desktop.mainwindow import MainWindow

    app = QApplication(sys.argv[:1])
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
