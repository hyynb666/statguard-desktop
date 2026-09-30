"""Presentation-only finding filtering and drag target validation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSortFilterProxyModel, Qt


class FindingFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.rule_id = "All Rules"
        self.severity = "All"
        self.confidence = "All"
        self.file_path = "All Files"
        self.search_text = ""
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def set_filters(
        self,
        *,
        rule_id: str = "All Rules",
        severity: str = "All",
        confidence: str = "All",
        file_path: str = "All Files",
        search_text: str = "",
    ) -> None:
        self.rule_id = rule_id
        self.severity = severity
        self.confidence = confidence
        self.file_path = file_path
        self.search_text = search_text.casefold().strip()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        model = self.sourceModel()
        rule = model.index(source_row, 0, source_parent).data()
        severity = model.index(source_row, 1, source_parent).data()
        confidence = model.index(source_row, 2, source_parent).data()
        file_path = model.index(source_row, 3, source_parent).data()
        finding = model.index(source_row, 0, source_parent).data(Qt.ItemDataRole.UserRole)
        if self.rule_id != "All Rules" and rule != self.rule_id:
            return False
        if self.severity != "All" and severity != self.severity:
            return False
        if self.confidence != "All" and confidence != self.confidence:
            return False
        if self.file_path != "All Files" and file_path != self.file_path:
            return False
        if self.search_text:
            searchable = " ".join(
                str(value)
                for value in (
                    rule,
                    file_path,
                    finding.message,
                    finding.explanation,
                    finding.suggestion,
                    finding.evidence,
                )
            ).casefold()
            if self.search_text not in searchable:
                return False
        return True


def validate_drop_paths(paths: list[str]) -> tuple[Path | None, str | None]:
    if len(paths) != 1:
        return None, "Please drop one Python file, Notebook, or folder."
    path = Path(paths[0])
    if path.is_dir() or (path.is_file() and path.suffix.lower() in {".py", ".ipynb"}):
        return path, None
    return None, "Unsupported scan target. Drop one .py, .ipynb, or folder."
