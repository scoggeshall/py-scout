# Py-Scout

Py-Scout is a GUI-first switchport discovery and physical mapping tool for Windows.

Core workflow:

```text
Plug in -> Run discovery -> See switch/port -> Save mapping -> Done
```

The packaged desktop app launches directly into the PySide6 interface:

```powershell
.\dist\pyscout.exe
```

## Requirements

- Windows
- Python 3.10 or newer for source/dev use
- Wireshark/TShark for LLDP/CDP discovery
- Npcap/Wireshark capture support
- Python dependencies from `requirements.txt`

Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

## Project Layout

```text
py-scout/
|- assets/
|- pyscout/
|  |- __main__.py
|  |- cli.py
|  |- core/
|  |- discovery/
|  |- gui/
|  \- storage/
|- tests/
|- build.ps1
|- py-scout.py
|- pyscout.spec
|- requirements.txt
\- README.md
```

Active product code lives in `pyscout/`. The public surface is intentionally limited to discovery, mapping, and the GUI.

## Desktop App

Build the single GUI/windowed executable:

```powershell
.\build.ps1
```

Expected output:

```text
dist\pyscout.exe
```

The build uses PyInstaller onefile/windowed mode, embeds `assets/pyscout.ico` from `assets/pyscout-taskbar-icon.png`, and bundles `assets/pyscout-logo.png` for in-app branding.

## Source CLI

The source CLI is intentionally minimal and intended for development checks only:

```powershell
python -m pyscout --help
python -m pyscout version
```

Running from source with no arguments opens the GUI:

```powershell
python -m pyscout
```

## Active Features

- PySide6 main window with Discovery and Mapper tabs
- TShark-based LLDP/CDP adapter discovery and packet parsing
- Mapper records persisted to SQLite
- GUI-first PyInstaller build producing `dist/pyscout.exe`

## Validation

Recommended checks:

```powershell
python -m unittest discover
python -m compileall pyscout
python -m pyscout --help
.\build.ps1
```

After building, double-click or run:

```powershell
.\dist\pyscout.exe
```

The app should launch the desktop GUI without opening a command prompt window.
