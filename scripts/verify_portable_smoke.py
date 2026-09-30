"""Validate reports emitted by an extracted portable EXE using Python's JSON parser."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--risk", type=Path, required=True)
    parser.add_argument("--safe", type=Path, required=True)
    parser.add_argument("--no-execution", type=Path, required=True)
    parser.add_argument("--notebook", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True)
    args = parser.parse_args()

    risk = load(args.risk)
    safe = load(args.safe)
    no_execution = load(args.no_execution)
    notebook = load(args.notebook)
    json_report = load(args.reports / "report.json")
    sarif_report = load(args.reports / "report.sarif")
    html_report = (args.reports / "report.html").read_text(encoding="utf-8")

    if "ML001" not in {finding["rule_id"] for finding in risk["findings"]}:
        raise SystemExit("The risk sample did not produce ML001.")
    if not any(
        "\u9879\u76ee 测试" in finding["file_path"]
        for finding in risk["findings"]
        if finding["rule_id"] == "ML001"
    ):
        raise SystemExit("The portable EXE did not preserve the Unicode scan path.")
    if "ML001" in {finding["rule_id"] for finding in safe["findings"]}:
        raise SystemExit("The safe sample incorrectly produced ML001.")
    if no_execution["analysis_errors"]:
        raise SystemExit("The non-execution Python smoke fixture did not scan successfully.")
    if "ML001" not in {finding["rule_id"] for finding in notebook["findings"]}:
        raise SystemExit("The Notebook sample did not produce ML001.")
    if not any(
        finding["rule_id"] == "ML001" and finding["cell_index"] == 1
        for finding in notebook["findings"]
    ):
        raise SystemExit("The Notebook finding did not retain its code-cell location.")
    if "PRIVATE_OUTPUT_SENTINEL" in json.dumps(notebook, ensure_ascii=False):
        raise SystemExit("Notebook output content was included in the scan result.")
    if json_report["schema_version"] != "1.0":
        raise SystemExit("JSON reporter schema is not 1.0.")
    if not any(finding["rule_id"] == "ML001" for finding in json_report["findings"]):
        raise SystemExit("The JSON report omitted the ML001 finding.")
    if sarif_report["version"] != "2.1.0":
        raise SystemExit("SARIF reporter schema is not 2.1.0.")
    if "Content-Security-Policy" not in html_report or "ML001" not in html_report:
        raise SystemExit("The HTML report is missing its CSP or ML001 finding.")
    print("Portable report and scan JSON: valid; Python, Notebook, HTML, JSON, SARIF: passed")


if __name__ == "__main__":
    main()
