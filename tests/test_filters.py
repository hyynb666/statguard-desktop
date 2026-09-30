from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QApplication

from statguard_desktop.filters import FindingFilterProxyModel, validate_drop_paths


def test_filter_model_combines_rule_severity_confidence_file_and_search() -> None:
    app = QApplication.instance() or QApplication([])

    class Finding:
        message = "Potential preprocessing leakage"
        explanation = "fitted before split"
        suggestion = "split first"
        evidence = "potential statistical risk"

    source = QStandardItemModel(0, 6)
    row = [
        QStandardItem(value) for value in ("ML001", "Warning", "High", "src/a.py", "3", "Leakage")
    ]
    row[0].setData(Finding(), Qt.ItemDataRole.UserRole)
    source.appendRow(row)
    other = [
        QStandardItem(value)
        for value in ("ST001", "Info", "Medium", "src/b.py", "9", "Multiple tests")
    ]
    other[0].setData(Finding(), Qt.ItemDataRole.UserRole)
    source.appendRow(other)

    proxy = FindingFilterProxyModel()
    proxy.setSourceModel(source)
    proxy.set_filters(
        rule_id="ML001",
        severity="Warning",
        confidence="High",
        file_path="src/a.py",
        search_text="SPLIT FIRST",
    )
    assert proxy.rowCount() == 1
    proxy.set_filters(search_text="no match")
    assert proxy.rowCount() == 0
    app.processEvents()


def test_filter_model_handles_large_finding_sets() -> None:
    app = QApplication.instance() or QApplication([])
    source = QStandardItemModel(0, 6)
    for index in range(500):
        rule_id = "ML001" if index % 2 == 0 else "ST001"
        row = [
            QStandardItem(value)
            for value in (rule_id, "Warning", "Medium", f"src/{index}.py", str(index), "finding")
        ]
        row[0].setData(
            SimpleNamespace(
                message="finding",
                explanation="test explanation",
                suggestion="test suggestion",
                evidence="potential statistical risk",
            ),
            Qt.ItemDataRole.UserRole,
        )
        source.appendRow(row)
    proxy = FindingFilterProxyModel()
    proxy.setSourceModel(source)
    proxy.set_filters(rule_id="ST001", search_text="finding")
    assert proxy.rowCount() == 250
    app.processEvents()


def test_drop_path_validation_accepts_single_supported_target(tmp_path) -> None:
    source = tmp_path / "x.py"
    source.write_text("pass\n")
    notebook = tmp_path / "x.ipynb"
    notebook.write_text("{}")
    assert validate_drop_paths([str(source)]) == (source, None)
    assert validate_drop_paths([str(notebook)]) == (notebook, None)
    assert validate_drop_paths([str(tmp_path)]) == (tmp_path, None)


def test_drop_path_validation_rejects_unsupported_or_multiple(tmp_path) -> None:
    other = tmp_path / "x.txt"
    other.write_text("no")
    rejected, error = validate_drop_paths([str(other)])
    assert rejected is None and "Unsupported" in error
    rejected, error = validate_drop_paths([str(other), str(tmp_path)])
    assert rejected is None and "one" in error
