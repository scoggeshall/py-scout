# py-scout

`py-scout` is a Windows-focused switchport lookup tool. It listens for LLDP and CDP advertisements with `tshark`, auto-selects a usable Ethernet adapter, and reports the first detected switch and port.

The project keeps the capture path simple:

- Windows adapter discovery uses PowerShell `Get-NetAdapter`
- Packet capture uses Wireshark/TShark
- Python runtime code stays in the standard library
- CLI and GUI both use the same scanner logic

## Requirements

- Windows
- Python 3.10 or newer
- Wireshark installed with `tshark` available on `PATH`
- Python with `tkinter` included if you want to use the GUI

Verify `tshark`:

```powershell
tshark -v
```

## Project Layout

```text
py-scout/
|- py_scout/
|  |- __init__.py
|  |- scanner.py
|  |- cli.py
|  \- gui.py
|- py-scout.py
|- build.ps1
|- requirements.txt
|- README.md
\- .gitignore
```

## Installation

Create and activate a virtual environment if you want an isolated Python install:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Runtime use does not require third-party Python packages. `requirements.txt` is only needed for optional executable builds.

## Download

Download release builds from GitHub Releases:

```text
https://github.com/scoggeshall/py-scout/releases
```

Verify the downloaded executable hash in PowerShell:

```powershell
Get-FileHash .\py-scout.exe -Algorithm SHA256
```

Published release assets should not be replaced after publishing. If the EXE
changes, publish a new release with a new SHA256 hash.

## CLI Usage

Launching Py-Scout with no arguments opens the GUI. To use command-line mode,
open PowerShell or Windows Terminal and pass the desired CLI options.

Auto-detect an active Ethernet adapter and wait up to 90 seconds:

```powershell
py .\py-scout.py --timeout 90
```

List available `tshark` interfaces:

```powershell
py .\py-scout.py --list
```

Use a specific Windows adapter name:

```powershell
py .\py-scout.py --interface "Ethernet"
```

Use a custom timeout:

```powershell
py .\py-scout.py --timeout 60
```

Show the built-in help:

```powershell
py .\py-scout.py --help
```

## JSON Output

Use `--json` for machine-readable output.

Scan result:

```powershell
py .\py-scout.py --json
```

Interface list:

```powershell
py .\py-scout.py --list --json
```

The JSON result includes:

- `timestamp`
- `adapter_name`
- `tshark_interface_number`
- `protocol`
- `switch`
- `port`
- `status`
- `timeout_seconds`

## Logging

Logging is optional and only records the scan result, not raw environment details.

Available flags:

- `--log-csv` appends results to `py-scout-log.csv`
- `--log-json` appends results to `py-scout-log.json`
- `--log-dir` sets the output directory and defaults to `logs`

Examples:

```powershell
py .\py-scout.py --log-csv
py .\py-scout.py --log-json
py .\py-scout.py --log-csv --log-json --log-dir .\logs
```

Each log entry includes:

- `timestamp`
- `adapter_name`
- `tshark_interface_number`
- `protocol`
- `switch`
- `port`
- `status`
- `timeout_seconds`

Status values include successful detections and timeout results.

## GUI Usage

Launch the tkinter GUI from source:

```powershell
py .\py-scout.py
```

You can also request the GUI explicitly:

```powershell
py .\py-scout.py --gui
```

The GUI provides:

- `Scan` to auto-select an Ethernet adapter and start a capture
- `List Interfaces` to display available `tshark` interfaces
- `Copy Result` to copy the current result text to the clipboard
- An optional timeout field
- An output area for adapter, protocol, switch, port, and scan status

If the current Python installation does not include `tkinter`, the GUI command exits with a clear error message.

## Executable Build

Install the optional build dependency:

```powershell
py -m pip install -r requirements.txt
```

Build the executable:

```powershell
.\build.ps1
```

Expected output:

```text
dist\py-scout.exe
```

Double-clicking `py-scout.exe` opens the GUI. Command-line usage still works
from PowerShell or Windows Terminal when arguments are provided:

```powershell
.\dist\py-scout.exe
.\dist\py-scout.exe --gui
.\dist\py-scout.exe --list
.\dist\py-scout.exe --timeout 10
```

## How It Works

1. Reads capture interfaces from `tshark -D`
2. Filters out Wi-Fi, Bluetooth, loopback, and common virtual adapters
3. Prefers Ethernet adapters with status `Up`
4. Captures LLDP or CDP traffic
5. Returns the first neighbor that contains a switch or port value

## Limitations

- The switchport must advertise LLDP or CDP for detection to work
- Some docks, pass-through phone ports, unmanaged switches, or filtered links may prevent discovery traffic from reaching the laptop
- Interface matching depends on Windows adapter naming and `tshark` interface naming lining up closely
- The tool is intentionally Windows-focused and relies on PowerShell adapter discovery
- Building the executable requires PyInstaller
- Using the GUI requires a Python installation that includes `tkinter`

## Validation

Recommended validation commands:

```powershell
python -m compileall .
py .\py-scout.py --list
py .\py-scout.py --help
```

If you want to verify timeout handling, disconnect Ethernet or test on a network where LLDP/CDP is not being advertised and run a short timeout:

```powershell
py .\py-scout.py --timeout 10
```
