from __future__ import annotations

import json

import pytest
import statguard

from statguard_desktop import adapter
from statguard_desktop.adapter import DesktopIntegrationError
from tests.helpers import RISKY_ML001, SAFE_ML001


def test_exact_engine_version_and_complete_registry() -> None:
    assert statguard.__version__ == "1.0.0"
    scanner, version = adapter._engine()
    assert version == "1.0.0"
    assert scanner.analyzer.registry.is_enabled("ML001")
    assert scanner.analyzer.registry.is_enabled("ML009")
    assert scanner.analyzer.registry.is_enabled("ST001")
    assert scanner.analyzer.registry.is_enabled("ST002")
    assert len(tuple(scanner.analyzer.registry.iter_enabled())) == 11


def test_version_mismatch_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(statguard, "__version__", "2.0.0")
    with pytest.raises(DesktopIntegrationError, match="requires StatGuard 1.0.0"):
        adapter.scan_metadata()


def test_scan_reports_actual_ml001_finding(tmp_path) -> None:
    source = tmp_path / "risk.py"
    source.write_text(RISKY_ML001, encoding="utf-8")
    report = adapter.scan_path(source)
    assert "ML001" in {item.rule_id for item in report.findings}
    payload = adapter.report_to_payload(report)
    assert payload["statguard_version"] == "1.0.0"
    assert payload["summary"]["warning"] == 1
    assert payload["findings"][0]["file_path"] == str(source)
    json.dumps(payload)


def test_safe_sample_has_no_findings(tmp_path) -> None:
    source = tmp_path / "safe.py"
    source.write_text(SAFE_ML001, encoding="utf-8")
    assert "ML001" not in {item.rule_id for item in adapter.scan_path(source).findings}


def test_missing_path_is_a_structured_analysis_error(tmp_path) -> None:
    report = adapter.scan_path(tmp_path / "missing.py")
    payload = adapter.report_to_payload(report)
    assert payload["findings"] == []
    assert payload["summary"]["failed_files"] == 0
    assert len(payload["analysis_errors"]) == 1
    assert payload["analysis_errors"][0]["stage"] == "parse"


def test_html_uses_core_reporter_and_keeps_findings(tmp_path) -> None:
    source = tmp_path / "risk.py"
    source.write_text(RISKY_ML001, encoding="utf-8")
    report = adapter.scan_path(source)
    rendered = adapter.render_report_html(report)
    assert "ML001" in rendered
    assert "Potential preprocessing leakage" in rendered


def test_unknown_engine_registry_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "default_registry", lambda: object())
    with pytest.raises(DesktopIntegrationError, match="invalid default rule registry"):
        adapter.scan_metadata()
