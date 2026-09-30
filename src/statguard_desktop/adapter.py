"""The sole boundary between the desktop UI and the pinned StatGuard engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import statguard
from statguard.analyzer import Analyzer
from statguard.reporters.html import render_html
from statguard.reporters.models import safe_error_message, summary
from statguard.rules import default_registry
from statguard.scanner import Scanner, ScanReport

from statguard_desktop import __version__ as desktop_version

SUPPORTED_CORE_VERSION = "1.0.0"
SUPPORTED_RULE_IDS = frozenset({*(f"ML{i:03}" for i in range(1, 10)), "ST001", "ST002"})


class DesktopIntegrationError(RuntimeError):
    """The installed analysis engine does not match this desktop release."""


def _engine() -> tuple[Scanner, str]:
    version = getattr(statguard, "__version__", "unknown")
    if version != SUPPORTED_CORE_VERSION:
        raise DesktopIntegrationError(
            "This desktop build requires StatGuard 1.0.0; "
            f"the installed engine is {version}. Reinstall the desktop package."
        )
    registry = default_registry()
    try:
        registered = frozenset(rule.rule_id for rule in registry)
        enabled = frozenset(rule.rule_id for rule in registry.iter_enabled())
    except (AttributeError, TypeError) as error:
        raise DesktopIntegrationError(
            "StatGuard 1.0.0 returned an invalid default rule registry."
        ) from error
    if registered != SUPPORTED_RULE_IDS:
        missing = ", ".join(sorted(SUPPORTED_RULE_IDS - registered)) or "none"
        unexpected = ", ".join(sorted(registered - SUPPORTED_RULE_IDS)) or "none"
        raise DesktopIntegrationError(
            "StatGuard 1.0.0 rule registry does not match the desktop contract "
            f"(missing: {missing}; unexpected: {unexpected})."
        )
    if enabled != SUPPORTED_RULE_IDS:
        raise DesktopIntegrationError(
            "StatGuard 1.0.0 did not enable its complete default rule set."
        )
    return Scanner(Analyzer(registry)), version


def scan_path(path: str | Path) -> ScanReport:
    """Scan a user-selected input using a fresh v1.0.0 default rule registry."""
    scanner, _ = _engine()
    return scanner.scan(path)


def report_to_payload(report: ScanReport) -> dict[str, Any]:
    """Project engine results to JSON-safe records without exposing AST objects."""
    totals = summary(report)
    return {
        "application": "StatGuard Desktop",
        "desktop_version": desktop_version,
        "statguard_version": SUPPORTED_CORE_VERSION,
        "summary": totals,
        "files": [
            {
                "path": result.path,
                "status": result.status.value,
                "findings": len(result.findings),
                "analysis_errors": len(result.errors),
            }
            for result in report.results
        ],
        "findings": [
            {
                "rule_id": item.rule_id,
                "severity": item.severity.value,
                "confidence": item.confidence.value,
                "evidence": item.evidence.value,
                "file_path": item.path,
                "line": item.line,
                "column": item.column,
                "cell_index": item.cell_index,
                "cell": item.cell,
                "message": item.message,
                "explanation": item.explanation,
                "suggestion": item.suggestion,
            }
            for item in report.findings
        ],
        "analysis_errors": [
            {
                "stage": error.stage.value,
                "code": error.code.value,
                "file_path": error.path,
                "rule_id": error.rule_id,
                "cell_index": error.cell_index,
                "cell": error.cell,
                "line": error.line,
                "column": error.column,
                "message": safe_error_message(error),
            }
            for error in report.analysis_errors
        ],
        "notices": [
            {
                "file_path": notice.path,
                "code": notice.code.value,
                "cell_index": notice.cell_index,
                "cell": notice.code_cell_index,
                "line": notice.line,
                "column": notice.column,
                "message": notice.message,
            }
            for result in report.results
            for notice in result.notices
        ]
        + [
            {"file_path": notice.path, "code": notice.code, "message": notice.message}
            for notice in report.scan_notices
        ],
    }


def render_report_html(report: ScanReport) -> str:
    """Render the engine's existing offline HTML report."""
    _engine()  # Guard version and registry before using the report renderer.
    return render_html(report)


def scan_metadata() -> dict[str, str]:
    """Return privacy-minimal build metadata for packaged-executable smoke checks."""
    _, version = _engine()
    return {
        "application": "StatGuard Desktop",
        "desktop_version": desktop_version,
        "statguard_version": version,
    }


def scan_smoke_payload(path: str | Path) -> dict[str, Any]:
    """Run the same scan adapter used by the GUI and return a machine-readable summary."""
    report = scan_path(path)
    payload = report_to_payload(report)
    payload["scanned_files"] = payload["summary"]["scanned_files"]
    return payload
