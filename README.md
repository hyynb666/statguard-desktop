# StatGuard Desktop

StatGuard Desktop is a small Windows GUI companion for the **StatGuard v1.0.0** static analysis engine. It lets you choose a Python file, Jupyter Notebook, or project folder, run the engine, review findings and analysis messages, and export the existing offline HTML report.

It is not a second analyzer. The application uses the exact v1.0.0 wheel from the core project's GitHub Release and does not fetch PyPI's latest StatGuard package. The GUI uses the core Scanner, default rule registry, Finding model, and HTML Reporter through one adapter.

## Use

Start `StatGuardDesktop.exe` from a Windows build, then choose a `.py` file, `.ipynb` file, or folder and press **Scan**. Select a finding to see its evidence, location, explanation, and suggestion. Use **Export HTML…** to save the core engine's offline report, then **Open HTML Report** to open it with the Windows default browser.

The default rule set contains ML001–ML009 and ST001–ST002. Findings are static-analysis signals, not proof that a workflow executed or that a statistical result is wrong. A clean scan does not establish statistical correctness. The desktop MVP does not provide UI for rule configuration, exclusions, or failure thresholds.

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

The MVP has no installer or code signing, auto-update, drag and drop, recent-file list, dark-mode switch, rule/configuration UI, or user-defined exclusion controls. It uses StatGuard's default rule configuration and the core HTML reporter.
