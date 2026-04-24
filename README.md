
---

# py-scout

Lightweight CLI tool to identify the **switch and port** a device is connected to using LLDP/CDP.

Built on top of **TShark**.

---

## Purpose

Replace guesswork and physical tracing with:

```text
plug in → run tool → get switch + port
```

Works by passively listening for:

* LLDP (standard)
* CDP (Cisco, preferred)

---

## Requirements

* Windows
* Python 3.10+
* Wireshark installed (provides `tshark`)

Verify:

```powershell
tshark -v
```

---

## Installation

```powershell
cd C:\scripts
mkdir py-scout
cd py-scout

py -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install pyshark
```

> Note: `pyshark` is optional; the tool uses `tshark` directly.

---

## Usage

### Auto-detect interface

```powershell
py .\py-scout.py
```

### List available interfaces

```powershell
py .\py-scout.py --list
```

### Manually specify interface

```powershell
py .\py-scout.py --interface "Ethernet"
```

### Custom timeout

```powershell
py .\py-scout.py --timeout 60
```

---

## How It Works

1. Reads capture interfaces from `tshark -D`
2. Filters for usable Ethernet adapters
3. Prefers adapters with status **Up**
4. Captures LLDP/CDP packets
5. Parses neighbor information
6. **Prefers CDP over LLDP**

Logic:

```text
LLDP arrives first → store
CDP arrives later → use CDP
No CDP → fallback to LLDP
```

---

## Interface Selection Logic

```text
1. Exclude:
   - Wi-Fi
   - Bluetooth
   - Loopback
   - Virtual adapters
   - VPN adapters

2. Select:
   - Ethernet adapters only

3. Prefer:
   - Status = Up

4. Fallback:
   - First valid Ethernet interface
```

---

## Limitations

This tool depends on the switch advertising:

### Will NOT work if:

* LLDP disabled
* CDP disabled
* Traffic filtered by:

  * IP phones (pass-through ports)
  * unmanaged switches
  * certain docks/adapters

---

## Troubleshooting

### No output

```powershell
py .\py-scout.py --list
```

Confirm:

* Correct adapter selected
* Status = Up

---

### Manual validation

```powershell
tshark -i <interface_number> -l -Y "lldp or cdp"
```

---

## Design Notes

* Uses raw `tshark` for reliability
* No dependency on fragile PowerShell parsing for selection
* Designed for **field use**

---

## Future Enhancements

* CSV / SQLite logging
* JSON output mode
* MAC address correlation
* Multi-interface scan mode
* Standalone executable build

---

## Bottom Line

```text
A portable switch-port identification tool
```

---