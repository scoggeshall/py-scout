# Py-Scout

Find exactly which switch port you're plugged into — instantly.

Plug in → run → get switch + port → save mapping → done.

---

## What you get

```text
Switch: MDF-SW01
Port: Gi1/0/24
IP: 10.16.1.45
Protocol: CDP
```

No digging through configs. No guessing. No tshark.

---

## Quick Start (10 seconds)

1. Download the latest release
2. Install Npcap (if prompted)
3. Run `pyscout.exe`
4. Click **Run Discovery**

---

## Why this exists

When you plug into a random wall jack, you usually don’t know:

* which switch you hit
* which port you're on
* where that drop goes

Py-Scout solves that immediately using LLDP/CDP.

---

## Features

* One-click switchport discovery (LLDP + CDP)
* Clean, readable output (no packet noise)
* Works as a single Windows `.exe`
* No tshark dependency
* Table-based mapper for tracking drops
* Manual or Auto Save of discovery results

---

## How it works

Py-Scout captures LLDP/CDP packets directly using Scapy and extracts:

* Switch name
* Port
* Neighbor IP
* Protocol
* Timestamp

Then lets you save and edit mappings.

---

## Requirements

* Windows
* Npcap (for packet capture)

If packet capture is missing, Py-Scout tells you clearly.

---

## Build (optional)

```powershell
python -m unittest discover
python -m compileall pyscout
.\build.ps1
.\dist\pyscout.exe
```

---

## Use cases

* Identify unknown wall jacks
* Map patch panels to switch ports
* Field troubleshooting
* Network documentation

---

## Bottom line

This replaces:

“Which switch port is this?”
“Let me trace cables…”

with:

Run → Answer

---

## Download

https://github.com/scoggeshall/py-scout/releases/latest
