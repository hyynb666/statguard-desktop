# Contributing

This repository is the separately maintained StatGuard Desktop companion. Keep it pinned to the exact StatGuard v1.0.0 release wheel unless a dedicated compatibility change is reviewed. Keep PySide6 within the tested 6.8 series unless a newer frozen build passes the packaged GUI launch test. Do not import or execute scanned modules, run Notebook cells, or inspect stored Notebook outputs.

## Local checks

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m build
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

Use `QT_QPA_PLATFORM=offscreen` for headless Qt tests. GUI changes should preserve responsive scanning, the read-only finding details, and core-generated HTML output.

## Scope

Keep the desktop UI focused on path selection, scanning, summary/findings review, and HTML export. Rule selection, configuration editing, recent scans, auto-updates, and installers are outside the MVP. Do not change or publish the StatGuard core repository from this project.
