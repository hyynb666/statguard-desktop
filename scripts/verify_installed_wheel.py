"""Run an adapter and reporter smoke against an installed Desktop wheel."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import statguard_desktop
from statguard_desktop.adapter import (
    engine_info_payload,
    render_report_html,
    render_report_json,
    render_report_sarif,
    scan_desktop,
    scan_metadata,
)


def main() -> None:
    installation = Path(statguard_desktop.__file__).resolve()
    environment = Path(sys.prefix).resolve()
    if environment not in installation.parents:
        raise SystemExit(
            f"Desktop was imported from outside the active environment: {installation}"
        )
    if statguard_desktop.__version__ != "0.1.0.dev0":
        raise SystemExit("Unexpected installed Desktop version.")
    metadata = scan_metadata()
    inventory = engine_info_payload()
    if metadata["statguard_version"] != "1.0.0" or len(inventory["enabled_rule_ids"]) != 11:
        raise SystemExit("The installed Desktop wheel did not load the pinned engine inventory.")

    root = Path.cwd()
    risk_path = root / "risk.py"
    safe_path = root / "safe.py"
    marker = root / "must-not-exist.marker"
    risk_path.write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        "from sklearn.preprocessing import StandardScaler\n"
        "from sklearn.model_selection import train_test_split\n"
        "scaler = StandardScaler()\n"
        "scaled = scaler.fit_transform(X)\n"
        "X_train, X_test = train_test_split(scaled)\n",
        encoding="utf-8",
    )
    safe_path.write_text("value = 1\n", encoding="utf-8")
    risk = scan_desktop(risk_path)
    safe = scan_desktop(safe_path)
    if "ML001" not in {item.rule_id for item in risk.report.findings}:
        raise SystemExit("Installed wheel did not report the ML001 sample.")
    if "ML001" in {item.rule_id for item in safe.report.findings}:
        raise SystemExit("Installed wheel reported ML001 for the safe sample.")
    if marker.exists():
        raise SystemExit("Installed wheel executed the scanned Python source.")

    notebook_path = root / "risk.ipynb"
    notebook_path.write_text(
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
                        "source": [
                            "from pathlib import Path\n",
                            f"Path({str(marker)!r}).write_text('executed')\n",
                            "from sklearn.preprocessing import StandardScaler\n",
                            "from sklearn.model_selection import train_test_split\n",
                            "scaler = StandardScaler()\n",
                            "scaled = scaler.fit_transform(X)\n",
                            "X_train, X_test = train_test_split(scaled)\n",
                        ],
                        "outputs": [{"output_type": "stream", "text": ["PRIVATE_OUTPUT_SENTINEL"]}],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    notebook = scan_desktop(notebook_path)
    if "ML001" not in {item.rule_id for item in notebook.report.findings}:
        raise SystemExit("Installed wheel did not analyze the Notebook code cell.")
    if marker.exists() or "PRIVATE_OUTPUT_SENTINEL" in str(notebook.report):
        raise SystemExit("Installed wheel executed or inspected Notebook output.")

    (root / "report.html").write_text(render_report_html(risk), encoding="utf-8")
    json_text = render_report_json(risk)
    json_payload = json.loads(json_text)
    (root / "report.json").write_text(json_text, encoding="utf-8")
    sarif_text = render_report_sarif(risk)
    sarif_payload = json.loads(sarif_text)
    (root / "report.sarif").write_text(sarif_text, encoding="utf-8")
    if json_payload["schema_version"] != "1.0" or sarif_payload["version"] != "2.1.0":
        raise SystemExit("Installed reporter schemas do not match the public contract.")
    if "Content-Security-Policy" not in (root / "report.html").read_text(encoding="utf-8"):
        raise SystemExit("Installed HTML report omitted its CSP.")
    print(f"Installed Desktop wheel smoke passed: {installation}")


if __name__ == "__main__":
    main()
