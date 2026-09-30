"""Background scan worker; potentially slow input processing never blocks the UI."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from statguard_desktop.adapter import DesktopScanResult, scan_desktop
from statguard_desktop.policy import DesktopScanPolicy


class ScanWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, path: str, policy: DesktopScanPolicy | None = None) -> None:
        super().__init__()
        self.path = path
        self.policy = policy

    @Slot()
    def run(self) -> None:
        try:
            report: DesktopScanResult = scan_desktop(self.path, self.policy)
        except Exception:  # Keep target-dependent exception details out of the GUI.
            self.failed.emit("Scan failed unexpectedly.")
        else:
            self.completed.emit(report)
