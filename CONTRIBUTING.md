# Contributing

This repository is the separately maintained StatGuard Desktop companion. Keep it pinned to the exact StatGuard v1.0.0 release wheel unless a dedicated compatibility change is reviewed. Keep PySide6 within the tested 6.8 series unless a newer frozen build passes the packaged GUI launch test. Do not import or execute scanned modules, run Notebook cells, or inspect stored Notebook outputs.

All StatGuard Core calls, including configuration loading, registry creation, scanning, threshold evaluation, and report rendering, belong in `statguard_desktop.adapter`. GUI code should only manage immutable policy snapshots and presentation. The project configuration selector intentionally checks the selected target's root (or selected file's parent) and does not walk ancestors. GUI overrides are temporary and must never write to project TOML files. Filtering and sorting must leave the stored full scan report unchanged; each export must render that last completed report without rescanning.

## Local checks

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m build
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\package_portable_windows.ps1
```

Use `QT_QPA_PLATFORM=offscreen` for headless Qt tests. GUI changes should preserve responsive background scanning, safe worker cleanup, read-only finding details, stable filtering, and Core-generated HTML, JSON, and SARIF output. Productization builds must keep version `0.1.0.dev0`, pin the exact Core 1.0.0 wheel and PySide6 `>=6.8.3,<6.9`, and avoid deleting any output outside `build/pyinstaller` and the named executable.

## Scope

Keep the desktop UI focused on path selection, temporary scan policy, finding review, and local report export. Recent scans, auto-updates, installers, and code signing remain outside scope. Do not change or publish the StatGuard core repository from this project.
