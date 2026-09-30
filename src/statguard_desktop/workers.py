"""Background scan worker; potentially slow input processing never blocks the UI."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from statguard_desktop.adapter import ScanReport, scan_path


class ScanWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path

    @Slot()
    def run(self) -> None:
        try:
            report: ScanReport = scan_path(self.path)
        except Exception as error:  # Surface a safe message; never show a traceback in the UI.
            self.failed.emit(f"{type(error).__name__}: {error}")
        else:
            self.completed.emit(report)
