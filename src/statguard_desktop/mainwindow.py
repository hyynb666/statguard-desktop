"""Desktop workflow for policy, scans, filtering, details, and report export."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QItemSelection, Qt, QThread, QUrl, Slot
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
    QIcon,
    QKeySequence,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
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
    DesktopScanResult,
    ScanReport,
    config_for_target,
    make_policy,
    render_report_html,
    render_report_json,
    render_report_sarif,
    rule_metadata,
    scan_metadata,
    threshold_reached,
)
from statguard_desktop.filters import FindingFilterProxyModel, validate_drop_paths
from statguard_desktop.policy import (
    CONFIG_CUSTOM,
    CONFIG_NONE,
    CONFIG_PROJECT,
    DesktopScanPolicy,
    validate_excludes,
)
from statguard_desktop.resources import resource_path
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
            + (f" (notebook cell {cell_index}), " if cell_index is not None else ", ")
            + location
        )
    return location


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        metadata = scan_metadata()
        self.rules = rule_metadata()
        self.setWindowTitle("StatGuard Desktop")
        self.setWindowIcon(QIcon(str(resource_path("assets/statguard-desktop.ico"))))
        self.resize(1250, 900)
        self.setMinimumSize(900, 600)
        self.last_result: DesktopScanResult | None = None
        self.last_html_path: Path | None = None
        self._thread: QThread | None = None
        self._worker: ScanWorker | None = None
        self._config_policy = DesktopScanPolicy()
        self._loading_config = False
        self._configuration_valid = True
        self.setAcceptDrops(True)
        self._build_ui(metadata["statguard_version"])
        self._build_menus()
        self.custom_config_path.setEnabled(False)
        self.browse_config_button.setEnabled(False)
        self._load_configuration()

    @property
    def last_report(self):
        """Compatibility view retained for the original MVP's integrations."""
        return self.last_result.report if self.last_result else None

    @last_report.setter
    def last_report(self, value) -> None:
        if value is None:
            self.last_result = None
        elif isinstance(value, DesktopScanResult):
            self.last_result = value
        else:
            self.last_result = DesktopScanResult(
                value, "", "", self._effective_policy(), self.rules
            )

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
        self.path_input.editingFinished.connect(self._load_configuration)
        self.browse_file_button = QPushButton("Browse File…")
        self.browse_file_button.setObjectName("browseFileButton")
        self.browse_folder_button = QPushButton("Browse Folder…")
        self.browse_folder_button.setObjectName("browseFolderButton")
        self.scan_button = QPushButton("Scan")
        self.scan_button.setObjectName("scanButton")
        self.scan_button.setDefault(True)
        self.clear_button = QPushButton("Clear")
        for button in (
            self.browse_file_button,
            self.browse_folder_button,
            self.scan_button,
            self.clear_button,
        ):
            button.setAccessibleName(button.text().replace("…", ""))
        path_row.addWidget(self.path_input, 1)
        path_row.addWidget(self.browse_file_button)
        path_row.addWidget(self.browse_folder_button)
        path_row.addWidget(self.scan_button)
        path_row.addWidget(self.clear_button)
        root.addLayout(path_row)

        config_box = QGroupBox("Configuration")
        config_grid = QGridLayout(config_box)
        self.config_source = QComboBox()
        self.config_source.addItems((CONFIG_PROJECT, CONFIG_NONE, CONFIG_CUSTOM))
        self.config_source.setObjectName("configSource")
        self.custom_config_path = QLineEdit()
        self.custom_config_path.setPlaceholderText("Select a TOML file")
        self.custom_config_path.setObjectName("customConfigPath")
        self.browse_config_button = QPushButton("Browse Config…")
        self.reload_config_button = QPushButton("Load / Reload")
        self.config_indicator = QLabel("Configuration: None")
        self.config_error = QLabel("")
        self.config_error.setStyleSheet("color: #a22")
        config_grid.addWidget(QLabel("Config source:"), 0, 0)
        config_grid.addWidget(self.config_source, 0, 1)
        config_grid.addWidget(self.custom_config_path, 0, 2)
        config_grid.addWidget(self.browse_config_button, 0, 3)
        config_grid.addWidget(self.reload_config_button, 0, 4)
        config_grid.addWidget(self.config_indicator, 1, 0, 1, 5)
        config_grid.addWidget(self.config_error, 2, 0, 1, 5)
        root.addWidget(config_box)

        settings_row = QHBoxLayout()
        rules_box = QGroupBox("Rules")
        rules_layout = QVBoxLayout(rules_box)
        self.rule_checks: dict[str, QCheckBox] = {}
        rule_grid = QGridLayout()
        for index, rule in enumerate(self.rules):
            check = QCheckBox(f"{rule.rule_id} · {rule.name}")
            check.setToolTip(rule.description)
            check.setChecked(True)
            check.stateChanged.connect(self._policy_changed)
            self.rule_checks[rule.rule_id] = check
            rule_grid.addWidget(check, index // 2, index % 2)
        rules_layout.addLayout(rule_grid)
        rule_buttons = QHBoxLayout()
        self.enable_all_button = QPushButton("Enable All")
        self.disable_all_button = QPushButton("Disable All")
        self.reset_rules_button = QPushButton("Reset to Config")
        self.enabled_count = QLabel("Enabled rules: 11 / 11")
        for button in (self.enable_all_button, self.disable_all_button, self.reset_rules_button):
            rule_buttons.addWidget(button)
        rule_buttons.addWidget(self.enabled_count)
        rules_layout.addLayout(rule_buttons)
        settings_row.addWidget(rules_box, 2)

        policy_box = QGroupBox("Scan Policy")
        policy_layout = QVBoxLayout(policy_box)
        self.fail_on = QComboBox()
        self.fail_on.addItem("None", None)
        self.fail_on.addItem("Warning", "warning")
        self.fail_on.addItem("Error", "error")
        self.fail_on.currentIndexChanged.connect(self._policy_changed)
        policy_layout.addWidget(QLabel("Fail on:"))
        policy_layout.addWidget(self.fail_on)
        self.threshold_status = QLabel("No failure threshold configured")
        policy_layout.addWidget(self.threshold_status)
        policy_layout.addWidget(QLabel("Excluded paths (directory scans only):"))
        self.exclude_list = QListWidget()
        self.exclude_list.setObjectName("excludeList")
        policy_layout.addWidget(self.exclude_list)
        exclude_buttons = QHBoxLayout()
        self.add_exclude_button = QPushButton("Add")
        self.remove_exclude_button = QPushButton("Remove")
        exclude_buttons.addWidget(self.add_exclude_button)
        exclude_buttons.addWidget(self.remove_exclude_button)
        policy_layout.addLayout(exclude_buttons)
        settings_row.addWidget(policy_box, 1)
        root.addLayout(settings_row)

        self.progress = QProgressBar()
        self.progress.setObjectName("scanProgress")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
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
            summary_grid.addWidget(value, 0, index)
            summary_grid.addWidget(QLabel(label), 1, index)
            self.summary_labels[key] = value
        root.addWidget(summary_box)

        filters_box = QGroupBox("Findings Filters")
        filters = QGridLayout(filters_box)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search findings…")
        self.rule_filter = QComboBox()
        self.severity_filter = QComboBox()
        self.severity_filter.addItems(("All", "Error", "Warning", "Info"))
        self.confidence_filter = QComboBox()
        self.confidence_filter.addItem("All")
        self.file_filter = QComboBox()
        self.file_filter.addItem("All Files")
        self.clear_filters_button = QPushButton("Clear Filters")
        self.visible_count = QLabel("Showing 0 of 0 findings")
        for col, (label, widget) in enumerate(
            (
                ("Search", self.search_input),
                ("Rule", self.rule_filter),
                ("Severity", self.severity_filter),
                ("Confidence", self.confidence_filter),
                ("File", self.file_filter),
            )
        ):
            filters.addWidget(QLabel(label), 0, col)
            filters.addWidget(widget, 1, col)
        filters.addWidget(self.clear_filters_button, 1, 5)
        filters.addWidget(self.visible_count, 2, 0, 1, 6)
        root.addWidget(filters_box)

        self.findings_model = QStandardItemModel(0, 6, self)
        self.findings_model.setHorizontalHeaderLabels(
            ("Rule", "Severity", "Confidence", "File", "Line", "Message")
        )
        self.proxy_model = FindingFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.findings_model)
        self.findings_view = QTableView()
        self.findings_view.setObjectName("findingsTable")
        self.findings_view.setModel(self.proxy_model)
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
        self.details.setPlaceholderText("Select a finding to inspect details.")
        self.copy_finding_button = QPushButton("Copy Finding")
        self.copy_finding_button.setEnabled(False)
        details_layout.addWidget(self.details)
        details_layout.addWidget(self.copy_finding_button)
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
        self.export_html_button = QPushButton("Export HTML…")
        self.export_html_button.setObjectName("exportHtmlButton")
        self.export_json_button = QPushButton("Export JSON…")
        self.export_sarif_button = QPushButton("Export SARIF…")
        self.open_html_button = QPushButton("Open HTML Report")
        self.open_html_button.setObjectName("openHtmlButton")
        self._export_buttons = (
            self.export_html_button,
            self.export_json_button,
            self.export_sarif_button,
        )
        for button in (*self._export_buttons, self.open_html_button):
            button.setEnabled(False)
        actions.addWidget(self.disclaimer, 1)
        for button in (*self._export_buttons, self.open_html_button):
            actions.addWidget(button)
        root.addLayout(actions)

        self.setCentralWidget(central)
        self.browse_file_button.clicked.connect(self._browse_file)
        self.browse_folder_button.clicked.connect(self._browse_folder)
        self.scan_button.clicked.connect(self.start_scan)
        self.clear_button.clicked.connect(self.clear_target)
        self.config_source.currentIndexChanged.connect(self._config_source_changed)
        self.browse_config_button.clicked.connect(self._browse_config)
        self.reload_config_button.clicked.connect(self._load_configuration)
        self.enable_all_button.clicked.connect(lambda: self._set_all_rules(True))
        self.disable_all_button.clicked.connect(lambda: self._set_all_rules(False))
        self.reset_rules_button.clicked.connect(self._reset_to_config)
        self.add_exclude_button.clicked.connect(self._add_exclude)
        self.remove_exclude_button.clicked.connect(self._remove_exclude)
        self.search_input.textChanged.connect(self._apply_filters)
        for combo in (
            self.rule_filter,
            self.severity_filter,
            self.confidence_filter,
            self.file_filter,
        ):
            combo.currentTextChanged.connect(self._apply_filters)
        self.clear_filters_button.clicked.connect(self._clear_filters)
        self.findings_view.selectionModel().selectionChanged.connect(self._show_selected_finding)
        self.copy_finding_button.clicked.connect(self._copy_finding)
        self.export_html_button.clicked.connect(lambda: self._export("html"))
        self.export_json_button.clicked.connect(lambda: self._export("json"))
        self.export_sarif_button.clicked.connect(lambda: self._export("sarif"))
        self.open_html_button.clicked.connect(self.open_html)
        self.config_source_changed = False
        self._update_rule_count()
        self._update_filter_count()

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        self._menu_actions = {}
        for key, label, shortcut, slot in (
            ("open_file", "Browse &File…", "Ctrl+O", self._browse_file),
            ("open_folder", "Browse F&older…", "Ctrl+Shift+O", self._browse_folder),
            ("clear", "&Clear", "Ctrl+L", self.clear_target),
        ):
            action = QAction(label, self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(slot)
            file_menu.addAction(action)
            self._menu_actions[key] = action
        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        self._menu_actions["exit"] = exit_action
        search_action = QAction("Focus &Search", self)
        search_action.setShortcut(QKeySequence("Ctrl+F"))
        search_action.triggered.connect(self.search_input.setFocus)
        file_menu.addAction(search_action)
        self._menu_actions["search"] = search_action
        help_menu = self.menuBar().addMenu("&Help")
        about_action = QAction("&About StatGuard Desktop", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        self._menu_actions["about"] = about_action

    @Slot()
    def _show_about(self) -> None:
        metadata = scan_metadata()
        QMessageBox.about(
            self,
            "About StatGuard Desktop",
            "<b>StatGuard Desktop</b><br>"
            f"Desktop {metadata['desktop_version']}<br>"
            f"Engine StatGuard {metadata['statguard_version']}<br><br>"
            "Static analysis for statistical Python workflows.<br>"
            "MIT License<br><br>"
            '<a href="https://github.com/hyynb666/statguard">StatGuard Core project</a>',
        )

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
            self._load_configuration()

    @Slot()
    def _browse_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select project folder", self.path_input.text()
        )
        if path:
            self.path_input.setText(path)
            self._load_configuration()

    @Slot()
    def _config_source_changed(self) -> None:
        self.custom_config_path.setEnabled(self.config_source.currentText() == CONFIG_CUSTOM)
        self.browse_config_button.setEnabled(self.config_source.currentText() == CONFIG_CUSTOM)
        self._load_configuration()

    @Slot()
    def _browse_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select StatGuard TOML configuration",
            self.custom_config_path.text(),
            "TOML files (*.toml);;All files (*)",
        )
        if path:
            self.custom_config_path.setText(path)
            self._load_configuration()

    @Slot()
    def _load_configuration(self) -> None:
        target = self.path_input.text().strip() or "."
        source = self.config_source.currentText()
        try:
            config, path = config_for_target(source, target, self.custom_config_path.text() or None)
            policy = make_policy(
                disabled_rules=config.disable_rules,
                exclude=config.exclude,
                fail_on=config.fail_on,
                config_source=source,
                config_path=path,
            )
        except (OSError, ValueError, RuntimeError) as error:
            self._configuration_valid = False
            self.config_error.setText(f"Invalid StatGuard configuration: {error}")
            return
        self._configuration_valid = True
        self.config_error.clear()
        self._config_policy = policy
        self._reset_to_config()
        self._update_exclude_state()

    def _reset_to_config(self) -> None:
        self._loading_config = True
        disabled = set(self._config_policy.disabled_rules)
        for rule_id, checkbox in self.rule_checks.items():
            checkbox.setChecked(rule_id not in disabled)
        self.exclude_list.clear()
        self.exclude_list.addItems(self._config_policy.exclude)
        index = self.fail_on.findData(self._config_policy.fail_on)
        self.fail_on.setCurrentIndex(max(index, 0))
        self._loading_config = False
        self._update_policy_indicator()
        self._update_rule_count()
        self._update_exclude_state()

    def _set_all_rules(self, enabled: bool) -> None:
        for checkbox in self.rule_checks.values():
            checkbox.setChecked(enabled)

    def _policy_changed(self, *_args) -> None:
        if self._loading_config:
            return
        self._update_rule_count()
        self._update_policy_indicator()

    def _update_rule_count(self) -> None:
        count = sum(checkbox.isChecked() for checkbox in self.rule_checks.values())
        self.enabled_count.setText(f"Enabled rules: {count} / {len(self.rule_checks)}")

    def _effective_policy(self) -> DesktopScanPolicy:
        disabled = tuple(
            rule_id for rule_id, check in self.rule_checks.items() if not check.isChecked()
        )
        exclude = tuple(self.exclude_list.item(i).text() for i in range(self.exclude_list.count()))
        return make_policy(
            disabled_rules=disabled,
            exclude=exclude,
            fail_on=self.fail_on.currentData(),
            config_source=self.config_source.currentText(),
            config_path=self._config_policy.config_path,
        )

    def _update_policy_indicator(self) -> None:
        try:
            current = self._effective_policy()
        except ValueError:
            current = None
        source = (
            self._config_policy.config_path
            if self._config_policy.config_source != CONFIG_NONE
            else "None"
        ) or "None"
        modified = current is not None and (
            current.disabled_rules != self._config_policy.disabled_rules
            or current.exclude != self._config_policy.exclude
            or current.fail_on != self._config_policy.fail_on
        )
        self.config_indicator.setText(
            f"Configuration: {source}" + (" · Modified in UI" if modified else "")
        )

    def _update_exclude_state(self) -> None:
        path = Path(self.path_input.text()) if self.path_input.text().strip() else None
        enabled = path is not None and path.is_dir()
        for widget in (self.exclude_list, self.add_exclude_button, self.remove_exclude_button):
            widget.setEnabled(enabled)
        self.exclude_list.setToolTip("" if enabled else "Exclusions apply to directory scans only.")

    @Slot()
    def _add_exclude(self) -> None:
        value, accepted = QInputDialog.getText(self, "Add excluded path", "Relative path:")
        if not accepted:
            return
        try:
            validate_excludes(
                [
                    *(self.exclude_list.item(i).text() for i in range(self.exclude_list.count())),
                    value,
                ]
            )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid excluded path", str(error))
            return
        if value.strip() not in [
            self.exclude_list.item(i).text() for i in range(self.exclude_list.count())
        ]:
            self.exclude_list.addItem(value.strip())
        self._update_policy_indicator()

    @Slot()
    def _remove_exclude(self) -> None:
        row = self.exclude_list.currentRow()
        if row >= 0:
            self.exclude_list.takeItem(row)
            self._update_policy_indicator()

    @Slot()
    def start_scan(self) -> None:
        if self._thread is not None:
            return
        if not self._configuration_valid:
            QMessageBox.warning(
                self,
                "Invalid StatGuard configuration",
                self.config_error.text() or "Reload a valid configuration before scanning.",
            )
            return
        path = self.path_input.text().strip()
        if not path:
            QMessageBox.warning(
                self, "Select an input", "Choose a .py file, .ipynb file, or folder."
            )
            return
        try:
            policy = self._effective_policy()
        except (ValueError, RuntimeError) as error:
            QMessageBox.warning(self, "Invalid scan policy", str(error))
            return
        self._set_scanning(True)
        self.progress.setRange(0, 0)
        self.progress.setFormat("Scanning…")
        self.threshold_status.setText("Checking threshold…")
        self.messages.clear()
        self.details.clear()
        self.copy_finding_button.setEnabled(False)
        self.findings_model.removeRows(0, self.findings_model.rowCount())
        self._clear_filter_values()
        self.empty_state.setText("Scanning…")
        self.empty_state.setVisible(True)
        for label in self.summary_labels.values():
            label.setText("—")
        self.last_result = None
        self.last_html_path = None
        self.open_html_button.setEnabled(False)
        for button in self._export_buttons:
            button.setEnabled(False)
        self._update_filter_count()

        thread = QThread(self)
        worker = ScanWorker(path, policy)
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
    def _scan_completed(self, result: DesktopScanResult) -> None:
        self.last_result = result
        self._populate_report(result)
        for button in self._export_buttons:
            button.setEnabled(True)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        errors = bool(result.report.analysis_errors)
        threshold = threshold_reached(result)
        if result.policy.fail_on is None:
            self.threshold_status.setText("No failure threshold configured")
        else:
            label = result.policy.fail_on.title()
            self.threshold_status.setText(
                f"{label} threshold reached" if threshold else "Threshold not reached"
            )
        self.progress.setFormat("Completed with analysis errors" if errors else "Scan complete")
        self.messages.appendPlainText(
            "Completed with analysis errors." if errors else "Scan complete."
        )

    @Slot(str)
    def _scan_failed(self, message: str) -> None:
        self.last_result = None
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("Scan failed")
        self.threshold_status.setText("No scan result")
        self.messages.setPlainText(f"Scan failed: {message}")
        self.empty_state.setText("Scan failed.")
        for button in self._export_buttons:
            button.setEnabled(False)
        self.open_html_button.setEnabled(False)

    @Slot()
    def _thread_finished(self) -> None:
        thread = self.sender()
        if thread is self._thread:
            self._worker = None
            self._thread = None
            thread.deleteLater()
            self._set_scanning(False)

    def _populate_report(self, result: DesktopScanResult | ScanReport) -> None:
        if isinstance(result, ScanReport):
            result = DesktopScanResult(result, "", "", self._effective_policy(), self.rules)
        report = result.report
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
            row = [
                QStandardItem(value)
                for value in (
                    finding.rule_id,
                    finding.severity.value.title(),
                    finding.confidence.value.title(),
                    finding.path,
                    str(finding.line),
                    finding.message,
                )
            ]
            row[4].setData(finding.line, Qt.ItemDataRole.DisplayRole)
            row[0].setData(finding, Qt.ItemDataRole.UserRole)
            row[3].setToolTip(finding.path)
            self.findings_model.appendRow(row)
        self._update_filter_choices(report)
        self._apply_filters()
        self.findings_view.resizeColumnsToContents()
        self.empty_state.setVisible(not report.findings)
        no_files = (
            Path(result.target_path).is_dir() and not report.results and not report.analysis_errors
        )
        self.empty_state.setText(
            "No supported .py or .ipynb files found."
            if no_files
            else "No findings reported. A clean scan does not establish statistical correctness."
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
        for result_item in report.results:
            for notice in result_item.notices:
                messages.append(f"NOTICE [{notice.code.value}] {notice.path}: {notice.message}")
        for notice in report.scan_notices:
            messages.append(f"NOTICE [{notice.code}] {notice.path}: {notice.message}")
        self.messages.setPlainText(
            "\n".join(messages)
            if messages
            else "No supported .py or .ipynb files found."
            if no_files
            else "No scan errors or notices."
        )

    def _update_filter_choices(self, report) -> None:
        findings = report.findings
        self._set_combo(self.rule_filter, "All Rules", sorted({f.rule_id for f in findings}))
        self._set_combo(self.file_filter, "All Files", sorted({f.path for f in findings}))
        confidence = sorted({f.confidence.value.title() for f in findings})
        self._set_combo(self.confidence_filter, "All", confidence)

    @staticmethod
    def _set_combo(combo: QComboBox, default: str, values: list[str]) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(default)
        combo.addItems(values)
        combo.blockSignals(False)

    @Slot()
    def _apply_filters(self, *_args) -> None:
        self.proxy_model.set_filters(
            rule_id=self.rule_filter.currentText() or "All Rules",
            severity=self.severity_filter.currentText() or "All",
            confidence=self.confidence_filter.currentText() or "All",
            file_path=self.file_filter.currentText() or "All Files",
            search_text=self.search_input.text(),
        )
        self.findings_view.selectionModel().clearSelection()
        self.details.clear()
        self.copy_finding_button.setEnabled(False)
        self._update_filter_count()

    def _update_filter_count(self) -> None:
        self.visible_count.setText(
            f"Showing {self.proxy_model.rowCount()} of {self.findings_model.rowCount()} findings"
        )

    def _clear_filter_values(self) -> None:
        self.search_input.clear()
        for combo, value in (
            (self.rule_filter, "All Rules"),
            (self.severity_filter, "All"),
            (self.confidence_filter, "All"),
            (self.file_filter, "All Files"),
        ):
            combo.setCurrentText(value)

    @Slot()
    def _clear_filters(self) -> None:
        self._clear_filter_values()
        self._apply_filters()

    @Slot(QItemSelection, QItemSelection)
    def _show_selected_finding(self, selected: QItemSelection, _deselected: QItemSelection) -> None:
        indexes = selected.indexes()
        if not indexes:
            self.details.clear()
            self.copy_finding_button.setEnabled(False)
            return
        source = self.proxy_model.mapToSource(indexes[0])
        finding = self.findings_model.item(source.row(), 0).data(Qt.ItemDataRole.UserRole)
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
        self.copy_finding_button.setEnabled(True)

    @Slot()
    def _copy_finding(self) -> None:
        QApplication.clipboard().setText(self.details.toPlainText())

    @Slot()
    def export_html(self) -> None:
        """Compatibility slot retained for the original HTML-only MVP."""
        self._export("html")

    @Slot()
    def _export(self, format_name: str) -> None:
        if self.last_result is None:
            return
        ext, renderer = {
            "html": ("html", render_report_html),
            "json": ("json", render_report_json),
            "sarif": ("sarif", render_report_sarif),
        }[format_name]
        default = f"statguard-report.{ext}"
        path, _ = QFileDialog.getSaveFileName(
            self, f"Export StatGuard {ext.upper()} report", default
        )
        if not path:
            return
        destination = Path(path)
        if destination.suffix.lower() != f".{ext}":
            destination = destination.with_suffix(f".{ext}")
        try:
            output = renderer(self.last_result)
            destination.write_text(output, encoding="utf-8")
        except (OSError, ValueError, RuntimeError) as error:
            QMessageBox.critical(self, "Report export failed", f"Could not write report: {error}")
            return
        self.statusBar().showMessage(f"Saved report: {destination}", 8000)
        if format_name == "html":
            self.last_html_path = destination
            self.open_html_button.setEnabled(True)

    @Slot()
    def open_html(self) -> None:
        if self.last_html_path is None:
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_html_path.resolve()))):
            QMessageBox.warning(
                self, "Could not open report", "Windows could not open the exported HTML file."
            )

    @Slot()
    def clear_target(self) -> None:
        self.path_input.clear()
        self.last_result = None
        self.last_html_path = None
        self.findings_model.removeRows(0, self.findings_model.rowCount())
        self.details.clear()
        self.messages.clear()
        self._clear_filters()
        for label in self.summary_labels.values():
            label.setText("—")
        self.empty_state.setText("Choose source files or a folder to start a scan.")
        self.empty_state.setVisible(True)
        self.progress.setFormat("Ready")
        self.threshold_status.setText("No scan result")
        self.copy_finding_button.setEnabled(False)
        for button in (*self._export_buttons, self.open_html_button):
            button.setEnabled(False)
        self._update_exclude_state()

    def _set_scanning(self, scanning: bool) -> None:
        widgets = [
            self.path_input,
            self.browse_file_button,
            self.browse_folder_button,
            self.scan_button,
            self.clear_button,
            self.config_source,
            self.custom_config_path,
            self.browse_config_button,
            self.reload_config_button,
            self.enable_all_button,
            self.disable_all_button,
            self.reset_rules_button,
            self.fail_on,
            self.exclude_list,
            self.add_exclude_button,
            self.remove_exclude_button,
            self.findings_view,
        ]
        widgets.extend(self.rule_checks.values())
        for widget in widgets:
            widget.setEnabled(not scanning)
        for button in (*self._export_buttons, self.open_html_button):
            button.setEnabled(
                not scanning
                and self.last_result is not None
                and (button is not self.open_html_button or self.last_html_path is not None)
            )

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        path, error = validate_drop_paths(paths)
        if error:
            self.statusBar().showMessage(error, 6000)
            event.ignore()
            return
        self.path_input.setText(str(path))
        self._load_configuration()
        self.statusBar().showMessage("Scan target selected. Press Scan to begin.", 5000)
        event.acceptProposedAction()

    def closeEvent(self, event: object) -> None:
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
        event.accept()
