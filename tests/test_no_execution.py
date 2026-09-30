from __future__ import annotations

import json

from statguard_desktop.adapter import report_to_payload, scan_path


def test_python_and_notebook_code_and_output_are_not_executed(tmp_path) -> None:
    marker = tmp_path / "must-not-exist.txt"
    python_file = tmp_path / "side_effect.py"
    python_file.write_text(
        "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n",
        encoding="utf-8",
    )
    notebook_file = tmp_path / "side_effect.ipynb"
    notebook_file.write_text(
        json.dumps(
            {
                "nbformat": 4,
                "nbformat_minor": 5,
                "metadata": {"kernelspec": {"language": "python"}},
                "cells": [
                    {
                        "cell_type": "code",
                        "metadata": {},
                        "execution_count": 1,
                        "outputs": [
                            {"output_type": "stream", "text": ["OUTPUT_SENTINEL", str(marker)]}
                        ],
                        "source": [
                            "from pathlib import Path\n",
                            f"Path({str(marker)!r}).write_text('executed')",
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    python_report = scan_path(python_file)
    notebook_report = scan_path(notebook_file)
    assert not python_report.analysis_errors
    assert not notebook_report.analysis_errors
    assert "OUTPUT_SENTINEL" not in str(report_to_payload(notebook_report))
    assert not marker.exists()
