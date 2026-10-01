from __future__ import annotations

import json

from statguard_desktop.__main__ import main
from tests.helpers import RISKY_ML001, SAFE_ML001


def test_metadata_smoke_mode_contains_no_machine_paths(tmp_path) -> None:
    destination = tmp_path / "metadata.json"
    assert main(["--smoke-test", str(destination)]) == 0
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload == {
        "application": "StatGuard Desktop",
        "desktop_version": "0.1.0",
        "statguard_version": "1.0.0",
    }
    assert str(tmp_path) not in destination.read_text(encoding="utf-8")


def test_engine_info_lists_every_pinned_rule_once_without_host_paths(tmp_path) -> None:
    destination = tmp_path / "engine.json"
    assert main(["--engine-info", str(destination)]) == 0
    payload = json.loads(destination.read_text(encoding="utf-8"))
    expected = [*(f"ML{i:03}" for i in range(1, 10)), "ST001", "ST002"]
    assert payload == {
        "desktop_version": "0.1.0",
        "statguard_version": "1.0.0",
        "enabled_rule_ids": expected,
    }
    assert str(tmp_path) not in destination.read_text(encoding="utf-8")


def test_gui_smoke_mode_constructs_and_shows_window(tmp_path) -> None:
    destination = tmp_path / "gui.json"
    assert main(["--gui-smoke-test", str(destination)]) == 0
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["window_title"] == "StatGuard Desktop"
    assert payload["scan_button_enabled"] is True
    assert payload["statguard_version"] == "1.0.0"


def test_scan_smoke_modes_risky_and_safe_inputs(tmp_path) -> None:
    risky = tmp_path / "risk.py"
    safe = tmp_path / "safe.py"
    risky.write_text(RISKY_ML001, encoding="utf-8")
    safe.write_text(SAFE_ML001, encoding="utf-8")
    risk_json = tmp_path / "risk.json"
    safe_json = tmp_path / "safe.json"

    assert main(["--scan-smoke", str(risky), str(risk_json)]) == 0
    assert main(["--scan-smoke", str(safe), str(safe_json)]) == 0
    risk_payload = json.loads(risk_json.read_text(encoding="utf-8"))
    safe_payload = json.loads(safe_json.read_text(encoding="utf-8"))
    assert "ML001" in {item["rule_id"] for item in risk_payload["findings"]}
    assert "ML001" not in {item["rule_id"] for item in safe_payload["findings"]}


def test_notebook_scan_smoke_uses_code_cell_only(tmp_path) -> None:
    source = tmp_path / "risk.ipynb"
    source.write_text(
        json.dumps(
            {
                "nbformat": 4,
                "nbformat_minor": 5,
                "metadata": {"kernelspec": {"language": "python"}},
                "cells": [
                    {
                        "cell_type": "code",
                        "metadata": {},
                        "execution_count": None,
                        "outputs": [],
                        "source": RISKY_ML001.splitlines(keepends=True),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    destination = tmp_path / "notebook.json"
    assert main(["--scan-smoke", str(source), str(destination)]) == 0
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert "ML001" in {item["rule_id"] for item in payload["findings"]}
    assert payload["findings"][0]["cell"] == 1


def test_packaged_report_smoke_writes_html_json_and_sarif(tmp_path) -> None:
    source = tmp_path / "safe.py"
    source.write_text(SAFE_ML001, encoding="utf-8")
    output = tmp_path / "reports"
    assert main(["--report-smoke", str(source), str(output)]) == 0
    html = (output / "report.html").read_text(encoding="utf-8")
    payload = json.loads((output / "report.json").read_text(encoding="utf-8"))
    sarif = json.loads((output / "report.sarif").read_text(encoding="utf-8"))
    assert "Content-Security-Policy" in html
    assert payload["schema_version"] == "1.0"
    assert sarif["version"] == "2.1.0"
