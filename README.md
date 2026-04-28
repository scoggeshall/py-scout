# Py-Scout

Py-Scout is a Windows-based switchport discovery and physical mapping tool.

It identifies the switch and port a device is connected to using LLDP/CDP and allows that mapping to be saved.

---

## Output

```text
Switch: MDF-SW01
Port: Gi1/0/24
IP: 10.16.1.45
Protocol: CDP
```

---

## Components

* Discovery

  * LLDP/CDP-based switchport identification
  * Normalized switch, port, IP, and protocol output
* Mapper

  * Save switchport-to-location mappings
  * Useful for documenting wall jacks, patch panels, and access-layer drops
* Network Scanner

  * Subnet scan
  * Optional hostname resolution
  * Optional common port checks
  * Best-effort device visibility, not a replacement for Nmap

---

## Requirements

* Windows
* Npcap
* LLDP or CDP enabled on the connected switchport

---

## Usage

1. Launch `pyscout.exe`
2. Run Discovery
3. View switch and port details
4. Optionally save the mapping
5. Use the Network Scanner for quick local subnet visibility

---

## Design Notes

* Uses Layer 2 discovery protocols
* Designed for access-layer troubleshooting
* Output is normalized for readability
* Mapper data is intended for practical field documentation

---

## Limitations

* Requires LLDP or CDP advertisements from the connected switchport
* Windows-only at this stage
* Scanner results are best-effort
* Port checks are intentionally basic

---

## Build

```powershell
python -m unittest discover
python -m compileall pyscout
.\build.ps1
```

---

## Repository

[https://github.com/scoggeshall/py-scout](https://github.com/scoggeshall/py-scout)
