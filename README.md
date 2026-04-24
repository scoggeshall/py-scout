
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

## Example Output

```text
Using adapter: Ethernet 2
Using tshark interface: 7
Waiting up to 90 seconds for LLDP/CDP...

Connected switchport found
--------------------------
Protocol : CDP
Switch   : EB9N-SWL2STACK.coj.net
Port     : GigabitEthernet2/0/15
```

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

> Note: `pyshark` is optional; core tool uses `tshark` directly.

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
py .\py-scout.py --interface "Ethernet 2"
```

### Custom timeout

```powershell
py .\py-scout.py --timeout 60
```

---

## How It Works

1. Reads available capture interfaces from `tshark -D`
2. Filters for usable Ethernet adapters
3. Prefers adapters that are **Up**
4. Captures LLDP/CDP packets
5. Parses:

* LLDP → System Name, Port ID
* CDP → Device ID, Port ID

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
   - VPN adapters (PANGP)

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

* LLDP disabled:

  ```cisco
  no lldp run
  ```

* CDP disabled:

  ```cisco
  no cdp enable
  ```

* Traffic blocked by:

  * IP phones (pass-through ports)
  * unmanaged switches
  * certain docks/adapters

---

## Troubleshooting

### No output

Run:

```powershell
py .\py-scout.py --list
```

Confirm:

* Correct adapter selected
* Status = Up

---

### Validate manually

```powershell
tshark -i <interface_number> -l -Y "lldp or cdp"
```

---

## Design Notes

* Uses raw `tshark` instead of wrappers for reliability
* Avoids PowerShell dependency for adapter detection
* Designed for **field use** (fast, deterministic)

---

## Future Enhancements

* CSV / SQLite logging
* JSON output mode
* MAC address correlation
* Multi-interface scan mode
* Packaging as standalone executable

---

## Bottom Line

This is not a packet analyzer.

This is:

```text
a portable switch-port identification tool
```

---