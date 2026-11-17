# PRO2052

Desktop companion for the RadioShack PRO-2052, maintained under the alias **pro2052**.

Version 1.0.0. Ukrainian and English interface, monitoring, channel editor, CSV import, backups and remote controls.

## Intel macOS build

Install Python 3.13 (or 3.12) with Tkinter from python.org, then run:

```bash
bash build.command
```

The build creates `dist/PRO2052.app` and `dist/PRO2052-1.0.0-Intel.dmg`.
The local build is ad-hoc signed, not Apple Developer ID signed or notarized.

## Windows build

Install 64-bit Python 3.13 or 3.12 with the Python launcher, then double-click `build-windows.cmd`.
The script builds from the same `src/` as macOS, runs the tests and verifies the packaged application.
Results in `dist/windows/`:

- `PRO2052/PRO2052.exe` and its required `_internal/` folder
- `PRO2052-1.0.0-Windows-x64.zip` for portable distribution
- `PRO2052-1.0.0-Setup.msi` for Program Files installation with shortcuts

The MSI retains user data on uninstall. Full installation/uninstallation requires validation on Windows with access to the Installer service. Builds are not publisher-signed.
Build outputs belong in GitHub Releases, not in the source repository.

## Run from source on Windows or macOS

Install Python with Tkinter, then:

```bash
python3 -m pip install -r src/requirements.txt
python3 src/launcher.py
```

On Windows use `python` instead of `python3` where appropriate.

## Tests

Application code lives in `src/`; automated tests live in `tests/`.
Run the full test suite on Windows with `python run_tests.py`.
The macOS build runs its selected checks with:

```bash
python3 run_tests.py test_macos test_programming test_periods
```

Tests are not bundled into the application.

## User data locations

- Windows: `%LOCALAPPDATA%/PRO2052`
- macOS: `~/Library/Application Support/PRO2052`

No personal settings, logs or channel inventories are included.
CSV frequency import requires reading all channels first. Review changes before confirming writes.
Physical scanner operation on macOS still requires hardware validation.

## Licensing

Third-party notices are preserved in `licenses/`. No open-source license has yet been granted for this application's original code. The included branded artwork is not a grant of trademark rights.
