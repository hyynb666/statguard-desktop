"""Small desktop workflow for choosing, scanning, reviewing, and exporting input."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QItemSelection, Qt, QThread, QUrl, Slot
from PySide6.QtGui import QDesktopServices, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from statguard_desktop.adapter import (
    ScanReport,
    render_report_html,
    scan_metadata,
)
from statguard_desktop.workers import ScanWorker


def _cell_location(finding: object) -> str:
    cell = getattr(finding, "cell", None)
    cell_index = getattr(finding, "cell_index", None)
    line = getattr(finding, "line", None)
    column = getattr(finding, "column", None)
    location = f"line {line}" if line is not None else "location unavailable"
    if column is not None:
        location += f", column {column}"
    if cell is not None:
        location = (
            f"code cell {cell}"
            + (f" (notebook cell {cell_index}), " if cell_index else ", ")
            + location
        )
    return location


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        metadata = scan_metadata()
        self.setWindowTitle("StatGuard Desktop")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)
        self.last_report: ScanReport | None = None
        self.last_html_path: Path | None = None
        self._thread: QThread | None = None
        self._worker: ScanWorker | None = None
        self._build_ui(metadata["statguard_version"])

    def _build_ui(self, engine_version: str) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        header = QHBoxLayout()
        title = QLabel("StatGuard Desktop")
        title.setObjectName("applicationTitle")
        title.setStyleSheet("font-size: 22px; font-weight: 650")
        powered = QLabel(f"Powered by StatGuard v{engine_version}")
        powered.setObjectName("engineVersion")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(powered)
        root.addLayout(header)

        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setObjectName("pathInput")
        self.path_input.setPlaceholderText("Choose a .py file, .ipynb Notebook, or project folder")
        self.browse_file_button = QPushButton("Browse File…")
        self.browse_file_button.setObjectName("browseFileButton")
        self.browse_folder_button = QPushButton("Browse Folder…")
        self.browse_folder_button.setObjectName("browseFolderButton")
        self.scan_button = QPushButton("Scan")
        self.scan_button.setObjectName("scanButton")
        self.scan_button.setDefault(True)
        path_row.addWidget(self.path_input, 1)
        path_row.addWidget(self.browse_file_button)
        path_row.addWidget(self.browse_folder_button)
        path_row.addWidget(self.scan_button)
        root.addLayout(path_row)

        self.progress = QProgressBar()
        self.progress.setObjectName("scanProgress")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("Ready")
        root.addWidget(self.progress)

        self.summary_labels: dict[str, QLabel] = {}
        summary_box = QGroupBox("Scan Summary")
        summary_grid = QGridLayout(summary_box)
        for index, (key, label) in enumerate(
            (
                ("files", "Files"),
                ("warnings", "Warnings"),
                ("info", "Info"),
                ("errors", "Error Findings"),
                ("analysis_errors", "Analysis Errors"),
            )
        ):
            value = QLabel("—")
            value.setObjectName(f"summary_{key}")
            caption = QLabel(label)
            summary_grid.addWidget(value, 0, index)
            summary_grid.addWidget(caption, 1, index)
            self.summary_labels[key] = value
        root.addWidget(summary_box)

        self.findings_model = QStandardItemModel(0, 6, self)
        self.findings_model.setHorizontalHeaderLabels(
            ("Rule", "Severity", "Confidence", "File", "Line", "Message")
        )
        self.findings_view = QTableView()
        self.findings_view.setObjectName("findingsTable")
        self.findings_view.setModel(self.findings_model)
        self.findings_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.findings_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.findings_view.setAlternatingRowColors(True)
        self.findings_view.setSortingEnabled(True)
        self.findings_view.horizontalHeader().setStretchLastSection(True)
        self.findings_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        root.addWidget(self.findings_view, 3)

        self.empty_state = QLabel("Choose source files or a folder to start a scan.")
        self.empty_state.setObjectName("emptyState")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.empty_state)

        details_box = QGroupBox("Finding Details")
        details_layout = QVBoxLayout(details_box)
        self.details = QPlainTextEdit()
        self.details.setObjectName("findingDetails")
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Select a finding to read its evidence and guidance.")
        details_layout.addWidget(self.details)
        root.addWidget(details_box, 2)

        messages_box = QGroupBox("Scan Messages")
        messages_layout = QVBoxLayout(messages_box)
        self.messages = QPlainTextEdit()
        self.messages.setObjectName("scanMessages")
        self.messages.setReadOnly(True)
        self.messages.setMaximumHeight(90)
        messages_layout.addWidget(self.messages)
        root.addWidget(messages_box)

        actions = QHBoxLayout()
        self.disclaimer = QLabel("A clean scan does not establish statistical correctness.")
        self.export_button = QPushButton("Export HTML…")
        self.export_button.setObjectName("exportHtmlButton")
        self.export_button.setEnabled(False)
        self.open_html_button = QPushButton("Open HTML Report")
        self.open_html_button.setObjectName("openHtmlButton")
        self.open_html_button.setEnabled(False)
        actions.addWidget(self.disclaimer, 1)
        actions.addWidget(self.export_button)
        actions.addWidget(self.open_html_button)
        root.addLayout(actions)

        self.setCentralWidget(central)
        self.browse_file_button.clicked.connect(self._browse_file)
        self.browse_folder_button.clicked.connect(self._browse_folder)
        self.scan_button.clicked.connect(self.start_scan)
        self.export_button.clicked.connect(self.export_html)
        self.open_html_button.clicked.connect(self.open_html)
        self.findings_view.selectionModel().selectionChanged.connect(self._show_selected_finding)

    @Slot()
    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Python source or Notebook",
            self.path_input.text(),
            "Python and Jupyter files (*.py *.ipynb)",
        )
        if path:
            self.path_input.setText(path)

    @Slot()
    def _browse_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select project folder", self.path_input.text()
        )
        if path:
            self.path_input.setText(path)

    @Slot()
    def start_scan(self) -> None:
        path = self.path_input.text().strip()
        if not path:
            QMessageBox.warning(
                self, "Select an input", "Choose a .py file, .ipynb file, or folder."
            )
            return
        self._set_scanning(True)
        self.progress.setRange(0, 0)
        self.progress.setFormat("Scanning…")
        self.messages.clear()
        self.details.clear()
        self.findings_model.removeRows(0, self.findings_model.rowCount())
        self.empty_state.setText("Scanning…")
        self.empty_state.setVisible(True)
        for label in self.summary_labels.values():
            label.setText("—")
        self.last_report = None
        self.last_html_path = None
        self.export_button.setEnabled(False)
        self.open_html_button.setEnabled(False)

        thread = QThread(self)
        worker = ScanWorker(path)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._scan_completed)
        worker.failed.connect(self._scan_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(self._thread_finished)
        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(object)
    def _scan_completed(self, report: ScanReport) -> None:
        self.last_report = report
        self._populate_report(report)
        self.export_button.setEnabled(True)
        self._set_scanning(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.progress.setFormat("Scan complete")

    @Slot(str)
    def _scan_failed(self, message: str) -> None:
        self._set_scanning(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("Scan failed")
        QMessageBox.critical(self, "Scan could not be completed", message)

    @Slot()
    def _thread_finished(self) -> None:
        thread = self.sender()
        if thread is self._thread:
            self._worker = None
            self._thread = None
            thread.deleteLater()

    def _populate_report(self, report: ScanReport) -> None:
        totals = {
            "files": len(report.results),
            "warnings": sum(item.severity.value == "warning" for item in report.findings),
            "info": sum(item.severity.value == "info" for item in report.findings),
            "errors": sum(item.severity.value == "error" for item in report.findings),
            "analysis_errors": len(report.analysis_errors),
        }
        for key, value in totals.items():
            self.summary_labels[key].setText(str(value))
        self.findings_model.removeRows(0, self.findings_model.rowCount())
        for finding in report.findings:
            values = (
                finding.rule_id,
                finding.severity.value,
                finding.confidence.value,
                finding.path,
                str(finding.line),
                finding.message,
            )
            row = [QStandardItem(value) for value in values]
            row[4].setData(finding.line, Qt.ItemDataRole.DisplayRole)
            row[0].setData(finding, Qt.ItemDataRole.UserRole)
            row[3].setToolTip(finding.path)
            self.findings_model.appendRow(row)
        self.findings_view.resizeColumnsToContents()
        self.empty_state.setVisible(not report.findings)
        self.empty_state.setText(
            "No findings reported. A clean scan does not establish statistical correctness."
        )
        messages: list[str] = []
        for error in report.analysis_errors:
            location = error.path
            if error.cell_index is not None:
                location += f" · notebook cell {error.cell_index}"
            if error.line is not None:
                location += f" · line {error.line}"
            messages.append(
                f"ERROR [{error.stage.value}/{error.code.value}] {location}: {error.message}"
            )
        for result in report.results:
            for notice in result.notices:
                location = notice.path
                if notice.cell_index is not None:
                    location += f" · notebook cell {notice.cell_index}"
                messages.append(f"NOTICE [{notice.code.value}] {location}: {notice.message}")
        for notice in report.scan_notices:
            messages.append(f"NOTICE [{notice.code}] {notice.path}: {notice.message}")
        self.messages.setPlainText(
            "\n".join(messages) if messages else "No scan errors or notices."
        )

    @Slot(QItemSelection, QItemSelection)
    def _show_selected_finding(self, selected: QItemSelection, _deselected: QItemSelection) -> None:
        if not selected.indexes():
            return
        index = selected.indexes()[0]
        finding = self.findings_model.item(index.row(), 0).data(Qt.ItemDataRole.UserRole)
        if finding is None:
            return
        evidence = getattr(finding.evidence, "value", finding.evidence)
        self.details.setPlainText(
            "\n".join(
                (
                    f"Rule: {finding.rule_id}",
                    f"Severity: {finding.severity.value}",
                    f"Confidence: {finding.confidence.value}",
                    f"Evidence: {evidence}",
                    f"Location: {finding.path} · {_cell_location(finding)}",
                    "",
                    f"Finding: {finding.message}",
                    "",
                    f"Risk: {finding.explanation}",
                    "",
                    f"Suggestion: {finding.suggestion}",
                )
            )
        )

    @Slot()
    def export_html(self) -> None:
        if self.last_report is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export StatGuard HTML report", "statguard-report.html", "HTML report (*.html)"
        )
        if not path:
            return
        destination = Path(path)
        if destination.suffix.lower() != ".html":
            destination = destination.with_suffix(".html")
        try:
            html = render_report_html(self.last_report)
            destination.write_text(html, encoding="utf-8")
        except (OSError, ValueError, RuntimeError) as error:
            QMessageBox.critical(
                self, "Report export failed", f"Could not write the HTML report: {error}"
            )
            return
        self.last_html_path = destination
        self.open_html_button.setEnabled(True)
        QMessageBox.information(self, "Report exported", f"Saved report to:\n{destination}")

    @Slot()
    def open_html(self) -> None:
        if self.last_html_path is None:
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_html_path.resolve()))):
            QMessageBox.warning(
                self, "Could not open report", "Windows could not open the exported HTML file."
            )

    def _set_scanning(self, scanning: bool) -> None:
        for widget in (
            self.path_input,
            self.browse_file_button,
            self.browse_folder_button,
            self.scan_button,
            self.findings_view,
        ):
            widget.setEnabled(not scanning)

    def closeEvent(self, event: object) -> None:
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
        event.accept()
