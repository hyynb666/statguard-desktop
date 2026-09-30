# StatGuard Desktop

StatGuard Desktop is a Windows GUI companion for the **StatGuard v1.0.0** static analysis engine. Select a Python file, Jupyter Notebook, or project folder, configure a scan, review findings, and export HTML, JSON, or SARIF reports.

It is not a second analyzer. The application uses the exact v1.0.0 wheel from the core project's GitHub Release and does not fetch PyPI's latest StatGuard package. Core configuration, rule registry, scanning, threshold evaluation, and reporters are accessed through one adapter.

## Use

Start `StatGuardDesktop.exe` from a Windows build, choose a `.py` file, `.ipynb` file, or folder and press **Scan**. A target can also be dragged onto the window; dropping selects it but does not start a scan. Select a finding to inspect its rule, evidence, location, explanation, and suggestion, or copy the detail as plain text.

### Configuration and rule controls

The Configuration selector supports **Project**, **None**, and **Custom TOML**. Project mode checks exactly one location: `<target directory>/pyproject.toml` for a directory target, or `<selected file parent>/pyproject.toml` for a file. It does not search ancestor directories. This target-root behavior is a Desktop UI policy and intentionally differs from the CLI's current-working-directory discovery.

None mode uses all 11 default rules, no exclusions, and no fail threshold. Custom TOML uses the StatGuard v1.0.0 loader and accepts only the Core-supported `[tool.statguard]` keys: `exclude`, `disable-rules`, and `fail-on`. Invalid config is shown in the app and prevents scanning until a valid configuration is loaded. Loaded settings initialize the UI; rules, exclusions, and fail-on may then be temporarily changed. The Desktop app never writes configuration back to `pyproject.toml`.

All rules ML001–ML009 and ST001–ST002 are listed with registry-provided names and descriptions. Use Enable All, Disable All, or Reset to Config; the enabled-rule count updates as checkboxes change. Exclusions are relative to the scanned directory and reject absolute paths or `..` traversal. Exclusions apply only to directory scans. Fail-on supports None, Warning, and Error; it reports threshold state in the UI and never closes the application.

### Finding filters and reports

The table can be filtered by rule, severity, confidence, and file, and searched case-insensitively across the rule ID, path, message, explanation, suggestion, and evidence. Filters and table sorting affect only presentation; exports contain the complete scan report, not only visible rows.

HTML, JSON schema 1.0, and SARIF 2.1.0 are rendered by the pinned Core reporter from the same completed scan. Exporting does not rescan. HTML can be opened with the Windows default browser; JSON and SARIF are saved locally.

Findings are static-analysis signals, not proof that a workflow executed or that a statistical result is wrong. A clean scan does not establish statistical correctness.

StatGuard reads source and Notebook code as data. It does not execute scanned Python or Notebook cells and does not inspect Notebook output content. Notebook cells are analyzed independently; document order is not proof of historical execution order.

## Development

Requires Python 3.11 or later. A development environment can install the pinned engine and desktop dependencies with:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m statguard_desktop
```

Run the checks with:

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

Build the Windows one-file, windowed executable with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

The output is `dist\StatGuardDesktop.exe`. The PyInstaller bundle includes the pinned StatGuard engine and Qt runtime; users do not need a separate Python or StatGuard installation. Windows is required to build and run the `.exe`; unit tests can also run on other supported Python platforms.

The build currently constrains PySide6 to the tested 6.8 series (`>=6.8.3,<6.9`): newer Qt wheels did not load in the validated one-file PyInstaller environment. Expanding the Qt range requires repeating the frozen-executable launch smoke test.

The executable supports hidden packaging smoke checks used by maintainers:

```powershell
.\dist\StatGuardDesktop.exe --smoke-test .\desktop-smoke.json
.\dist\StatGuardDesktop.exe --scan-smoke .\sample.py .\scan-smoke.json
```

## Core project

StatGuard core: <https://github.com/hyynb666/statguard> · [v1.0.0 release](https://github.com/hyynb666/statguard/releases/tag/v1.0.0)

This desktop project is maintained separately from the core repository. It does not publish a core release, create tags, upload packages, or change core versioning.

## Current limits

The application has no installer or code signing, auto-update, recent-file list, dark-mode-specific theme, or source-editor integration. Configuration changes are temporary UI overrides and are never saved back to project files.
