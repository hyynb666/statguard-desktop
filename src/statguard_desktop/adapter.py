"""The sole boundary between the desktop UI and the pinned StatGuard engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import statguard
from statguard.analyzer import Analyzer
from statguard.config import ConfigError, StatGuardConfig, discover_config, load_config
from statguard.reporters import RuleMetadata, render_html, render_json, render_sarif
from statguard.reporters.models import reaches_threshold, safe_error_message, summary
from statguard.rules import default_registry
from statguard.scanner import Scanner, ScanReport

from statguard_desktop import __version__ as desktop_version
from statguard_desktop.policy import (
    CONFIG_CUSTOM,
    CONFIG_NONE,
    CONFIG_PROJECT,
    DesktopScanPolicy,
    project_config_path,
    validate_excludes,
)

SUPPORTED_CORE_VERSION = "1.0.0"
SUPPORTED_RULE_IDS = frozenset({*(f"ML{i:03}" for i in range(1, 10)), "ST001", "ST002"})


class DesktopIntegrationError(RuntimeError):
    """The installed analysis engine does not match this desktop release."""


@dataclass(frozen=True, slots=True)
class RuleInfo:
    rule_id: str
    name: str
    description: str
    severity: str


@dataclass(frozen=True, slots=True)
class DesktopScanResult:
    report: ScanReport
    target_path: str
    base_path: str
    policy: DesktopScanPolicy
    rules: tuple[RuleInfo, ...]


def _engine_with_metadata(
    disabled_rules: tuple[str, ...] = (),
) -> tuple[Scanner, str, tuple[RuleInfo, ...]]:
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
    metadata = tuple(
        RuleInfo(
            rule_id=rule.rule_id,
            name=rule.name,
            description=rule.description,
            severity=rule.default_severity.value,
        )
        for rule in registry
    )
    unknown = sorted(set(disabled_rules) - SUPPORTED_RULE_IDS)
    if unknown:
        raise ConfigError(f"unknown rule ID: {unknown[0]}")
    for rule_id in disabled_rules:
        registry.disable(rule_id)
    return Scanner(Analyzer(registry)), version, metadata


def _engine() -> tuple[Scanner, str]:
    """Keep the original MVP's internal two-value helper contract."""
    scanner, version, _metadata = _engine_with_metadata()
    return scanner, version


def rule_metadata() -> tuple[RuleInfo, ...]:
    """Read rule labels from the pinned core registry, without running rules."""
    return _engine_with_metadata()[2]


def config_for_target(
    source: str, target: str | Path, custom_path: str | Path | None = None
) -> tuple[StatGuardConfig, str | None]:
    """Load a core policy from one explicit project root or custom TOML file."""
    if source == CONFIG_NONE:
        return StatGuardConfig(), None
    if source == CONFIG_PROJECT:
        path = project_config_path(target)
        config = discover_config(path)
    elif source == CONFIG_CUSTOM:
        if custom_path is None:
            raise ConfigError("Choose a custom TOML configuration file")
        path = Path(custom_path)
        config = load_config(path)
    else:
        raise ConfigError("Choose Project, None, or Custom TOML configuration")
    make_policy(
        disabled_rules=config.disable_rules,
        exclude=config.exclude,
        fail_on=config.fail_on,
        config_source=source,
        config_path=str(path),
    )
    return config, str(path)


def make_policy(
    *,
    disabled_rules: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
    fail_on: str | None = None,
    config_source: str = CONFIG_PROJECT,
    config_path: str | None = None,
) -> DesktopScanPolicy:
    if fail_on not in (None, "warning", "error"):
        raise ValueError("fail-on must be None, warning, or error")
    if set(disabled_rules) - SUPPORTED_RULE_IDS:
        raise ConfigError("Configuration contains an unknown rule ID")
    return DesktopScanPolicy(
        tuple(sorted(set(disabled_rules))),
        validate_excludes(exclude),
        fail_on,
        config_source,
        config_path,
    )


def scan_desktop(path: str | Path, policy: DesktopScanPolicy | None = None) -> DesktopScanResult:
    """Scan once using a policy snapshot, preserving the complete core report."""
    target = Path(path).resolve()
    effective = policy or make_policy()
    scanner, _version, metadata = _engine_with_metadata(effective.disabled_rules)
    report = scanner.scan(target, exclude=effective.exclude)
    base_path = target if target.is_dir() else target.parent
    return DesktopScanResult(report, str(target), str(base_path), effective, metadata)


def scan_path(path: str | Path) -> ScanReport:
    """Backward-compatible basic scan entry point used by the original MVP."""
    return scan_desktop(path).report


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


def render_report_html(result: DesktopScanResult | ScanReport) -> str:
    """Render the engine's existing offline HTML report."""
    _engine()  # Guard version and registry before using the report renderer.
    return render_html(result.report if isinstance(result, DesktopScanResult) else result)


def render_report_json(result: DesktopScanResult) -> str:
    _engine()
    return render_json(result.report)


def render_report_sarif(result: DesktopScanResult) -> str:
    _engine()
    metadata = {
        item.rule_id: RuleMetadata(item.name, item.description, item.severity)
        for item in result.rules
    }
    return render_sarif(result.report, base_path=result.base_path, rule_metadata=metadata)


def threshold_reached(result: DesktopScanResult) -> bool:
    return reaches_threshold(result.report, result.policy.fail_on)


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
