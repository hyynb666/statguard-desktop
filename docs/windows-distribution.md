# Windows distribution

The v0.1 desktop distribution target is Windows 10/11 on 64-bit AMD64. The standalone executable is a PyInstaller one-file, windowed application; it bundles the exact StatGuard 1.0.0 wheel and the PySide6 runtime. Users do not need Python or a separate Core installation. ARM64, 32-bit Windows, macOS, and Linux desktop binaries are not release-validated.

The recommended distribution is a portable ZIP. It needs no administrator rights, registry writes, or uninstaller and is proportionate for this small open-source developer tool. Inno Setup would add installer and uninstall behavior; MSIX would add packaging/signing and deployment requirements. Neither is needed for this candidate. There is no installer, auto-update, telemetry, source upload, or code-signing certificate. The current development executable is unsigned, so Windows may show an unknown-publisher warning. Do not disable Windows security features as a workaround.

The portable RC folder and ZIP are generated locally by `scripts/package_portable_windows.ps1` after `scripts/build_windows.ps1`. The build records Desktop, Core, Python, PySide6, PyInstaller, platform, architecture, and executable SHA-256 in ignored `build/` metadata. No username, hostname, or repository path is recorded. The package contains only the EXE, a short user README, the project LICENSE, and their SHA-256 manifest.

The app uses an original project-owned shield/check icon in the window and executable. Runtime dependencies are PySide6 (`>=6.8.3,<6.9`) and the exact StatGuard 1.0.0 release wheel, plus PySide6's transitive runtime dependencies. StatGuard Core itself declares no runtime dependencies. Scanning remains static: submitted Python and Notebook cells are not executed, Notebook outputs are ignored, and the application has no runtime network features.

Release verification checks include the executable's Windows version resource, engine inventory, smoke scans from an extracted ZIP, Unicode paths, report formats, and non-execution fixtures. High-DPI layout still needs manual visual confirmation at 125% and 150% scaling on Windows.
