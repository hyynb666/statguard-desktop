# StatGuard Desktop v0.1.0

StatGuard Desktop v0.1.0 is the first public Alpha release of the **Windows desktop companion for StatGuard v1.0.0**. It packages the pinned static analysis engine into a standalone GUI for Python and Jupyter Notebook projects.

## Download

Download the recommended portable ZIP from the [v0.1.0 release page](https://github.com/hyynb666/statguard-desktop/releases/tag/v0.1.0): **StatGuard-Desktop-0.1.0-windows-x64.zip**. Extract it and double-click `StatGuardDesktop.exe`. A standalone [`StatGuardDesktop.exe`](https://github.com/hyynb666/statguard-desktop/releases/download/v0.1.0/StatGuardDesktop.exe) is also available. The ZIP is recommended because it includes a README, MIT license, and checksums.

Requirements: **Windows 10/11, 64-bit x86_64/AMD64**. No Python installation or separate StatGuard installation is required. The executable is not code-signed; Windows SmartScreen may show an unknown-publisher warning. Do not disable Defender or SmartScreen.

## Use

1. Download and extract the portable ZIP.
2. Double-click `StatGuardDesktop.exe`.
3. Select or drop a `.py` file, `.ipynb` file, or project folder.
4. Choose project, custom, or no configuration; enable or disable rules and set exclusions or a fail-on policy if desired.
5. Scan, filter and search findings, inspect details, and export HTML, JSON schema 1.0, or SARIF 2.1.0.

The GUI supports Python and Notebook file scans, recursive directory scans, drag and drop, rule and policy controls, finding filters/search, finding details, copy finding, and local HTML/JSON/SARIF export. It includes the 11 rules shipped with StatGuard Core 1.0.0 (ML001–ML009 and ST001–ST002).

Configuration changes in the GUI are temporary and are not written back to project files. The app has no scan cancellation, installer, auto-update, telemetry, source-editor integration, or network upload.

## Safety and limits

StatGuard Desktop performs static analysis. It does not execute submitted Python source or Notebook code and does not analyze Notebook outputs. A clean scan does not prove statistical correctness. The analyzer supports explicit static patterns; it does not infer across files or Notebook cells beyond the Core's documented capabilities.

The v0.1.0 binary supports Windows x64 only; there are no supported ARM64, 32-bit, macOS, or Linux Desktop binaries. The application has no automatic updates.

## Development

Source/development installation supports CPython **3.11–3.13**. PySide6 is constrained to `>=6.8.3,<6.9`; its 6.8.3 metadata excludes Python 3.14. Windows x64 is required to build and run the frozen executable. See [Windows distribution notes](docs/windows-distribution.md) and [CONTRIBUTING](CONTRIBUTING.md).

## Core project

StatGuard Core: <https://github.com/hyynb666/statguard> · [v1.0.0 release](https://github.com/hyynb666/statguard/releases/tag/v1.0.0)
