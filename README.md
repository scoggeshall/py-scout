# Py-Scout

Py-Scout is a GUI-first switchport discovery and physical mapping tool for Windows.

It identifies the switch and port a device is connected to using LLDP/CDP, then allows you to persist that mapping.

---

## Quick example

```text
Switch: MDF-SW01
Port: Gi1/0/24
IP: 10.16.1.45
Protocol: CDP
```

---

## Core workflow

Plug in → Run discovery → See switch/port → Save mapping

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
