from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


BAD_INTERFACE_WORDS = (
    "wi-fi",
    "wireless",
    "bluetooth",
    "loopback",
    "pangp",
    "virtual",
    "local area connection",
    "etw",
)


class ScannerError(RuntimeError):
    """Raised when py-scout cannot enumerate or scan an interface."""


@dataclass(slots=True)
class InterfaceRecord:
    number: str
    device: str
    name: str
    raw: str
    status: str = "unknown"
    role: str = "skip"


@dataclass(slots=True)
class SelectedInterface:
    number: str
    name: str


@dataclass(slots=True)
class ScanResult:
    timestamp: str
    adapter_name: str
    tshark_interface_number: str
    protocol: str | None
    switch: str | None
    port: str | None
    status: str
    timeout_seconds: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def new_failure_result(
    timeout_seconds: int,
    *,
    status: str = "failure",
    adapter_name: str | None = None,
    tshark_interface_number: str | None = None,
) -> ScanResult:
    return ScanResult(
        timestamp=datetime.now().astimezone().isoformat(timespec="seconds"),
        adapter_name=adapter_name or "unknown",
        tshark_interface_number=tshark_interface_number or "unknown",
        protocol=None,
        switch=None,
        port=None,
        status=status,
        timeout_seconds=timeout_seconds,
    )


def run_cmd(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True)


def is_bad_interface(name: str) -> bool:
    lowered = name.lower()
    return any(word in lowered for word in BAD_INTERFACE_WORDS)


def get_tshark_interfaces() -> list[InterfaceRecord]:
    try:
        result = run_cmd(["tshark", "-D"])
    except FileNotFoundError as exc:
        raise ScannerError("ERROR: tshark not found or not working.") from exc

    if result.returncode != 0:
        message = "ERROR: tshark not found or not working."
        detail = result.stderr.strip()
        if detail:
            message = f"{message}\n{detail}"
        raise ScannerError(message)

    interfaces: list[InterfaceRecord] = []

    for line in result.stdout.splitlines():
        match = re.match(r"^(\d+)\.\s+(.+?)\s+\((.+)\)$", line.strip())
        if not match:
            continue

        number, device, name = match.groups()
        interfaces.append(
            InterfaceRecord(
                number=number.strip(),
                device=device.strip(),
                name=name.strip(),
                raw=line.strip(),
            )
        )

    return interfaces


def get_windows_adapters() -> dict[str, dict[str, Any]]:
    ps = (
        "Get-NetAdapter | "
        "Select-Object Name,InterfaceDescription,Status,MacAddress,LinkSpeed | "
        "ConvertTo-Json -Compress"
    )

    try:
        result = run_cmd(["powershell", "-NoProfile", "-Command", ps])
    except FileNotFoundError:
        return {}

    if result.returncode != 0 or not result.stdout.strip():
        return {}

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}

    if isinstance(data, dict):
        data = [data]

    adapters: dict[str, dict[str, Any]] = {}

    for item in data:
        name = str(item.get("Name", "")).strip()
        if name:
            adapters[name.lower()] = item

    return adapters


def is_adapter_up(interface_name: str, adapters: dict[str, dict[str, Any]]) -> bool:
    adapter = adapters.get(interface_name.lower())
    if not adapter:
        return False

    return str(adapter.get("Status", "")).lower() == "up"


def get_interface_inventory() -> list[InterfaceRecord]:
    interfaces = get_tshark_interfaces()
    adapters = get_windows_adapters()

    for iface in interfaces:
        adapter = adapters.get(iface.name.lower())
        iface.status = str(adapter.get("Status", "unknown")) if adapter else "unknown"

        if is_bad_interface(iface.name):
            iface.role = "skip"
        elif "ethernet" in iface.name.lower() and iface.status.lower() == "up":
            iface.role = "candidate/up"
        elif "ethernet" in iface.name.lower():
            iface.role = "candidate/down"
        else:
            iface.role = "skip"

    return interfaces


def auto_select_tshark_interface() -> SelectedInterface | None:
    interfaces = get_interface_inventory()

    ethernet_candidates = [
        iface
        for iface in interfaces
        if "ethernet" in iface.name.lower() and not is_bad_interface(iface.name)
    ]

    if not ethernet_candidates:
        return None

    up_candidates = [
        iface for iface in ethernet_candidates if iface.status.lower() == "up"
    ]

    if up_candidates:
        return SelectedInterface(number=up_candidates[0].number, name=up_candidates[0].name)

    return SelectedInterface(
        number=ethernet_candidates[0].number,
        name=ethernet_candidates[0].name,
    )


def get_tshark_interface_number(adapter_name: str) -> str | None:
    interfaces = get_tshark_interfaces()

    for iface in interfaces:
        if iface.name.lower() == adapter_name.lower():
            return iface.number

    return None


def resolve_capture_interface(adapter_name: str | None) -> SelectedInterface:
    if adapter_name:
        iface_num = get_tshark_interface_number(adapter_name)
        if not iface_num:
            raise ScannerError(
                f"ERROR: Could not map Windows adapter '{adapter_name}' to tshark interface.\n"
                "Run: py .\\py-scout.py --list"
            )

        return SelectedInterface(number=iface_num, name=adapter_name)

    selected = auto_select_tshark_interface()
    if selected is None:
        raise ScannerError(
            "ERROR: Could not auto-select an active Ethernet capture interface.\n"
            "Run: py .\\py-scout.py --list"
        )

    return selected


def parse_neighbor(line: str) -> dict[str, str | None]:
    result: dict[str, str | None] = {
        "protocol": None,
        "switch": None,
        "port": None,
        "raw": line.strip(),
    }

    if "LLDP" in line:
        result["protocol"] = "LLDP"

        sys_match = re.search(r"SysN=([^\s]+)", line)
        port_match = re.search(r"\bIN/([^\s,]+)", line)

        if sys_match:
            result["switch"] = sys_match.group(1)

        if port_match:
            result["port"] = port_match.group(1)

    elif "CDP" in line:
        result["protocol"] = "CDP"

        sys_match = re.search(r"Device ID:\s+(.+?)\s+Port ID:", line)
        port_match = re.search(r"Port ID:\s+([^\s,]+)", line)

        if sys_match:
            result["switch"] = sys_match.group(1).strip()

        if port_match:
            result["port"] = port_match.group(1).strip()

    return result


def new_scan_result(
    selected: SelectedInterface,
    timeout_seconds: int,
    *,
    protocol: str | None = None,
    switch: str | None = None,
    port: str | None = None,
    status: str = "timeout",
) -> ScanResult:
    return ScanResult(
        timestamp=datetime.now().astimezone().isoformat(timespec="seconds"),
        adapter_name=selected.name,
        tshark_interface_number=selected.number,
        protocol=protocol,
        switch=switch,
        port=port,
        status=status,
        timeout_seconds=timeout_seconds,
    )


def scan_on_interface(selected: SelectedInterface, timeout_seconds: int) -> ScanResult:
    cmd = [
        "tshark",
        "-i",
        str(selected.number),
        "-a",
        f"duration:{timeout_seconds}",
        "-l",
        "-Y",
        "lldp or cdp",
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except FileNotFoundError as exc:
        raise ScannerError("ERROR: tshark not found or not working.") from exc

    result = new_scan_result(selected, timeout_seconds, status="timeout")

    try:
        assert proc.stdout is not None

        for line in proc.stdout:
            neighbor = parse_neighbor(line)
            if neighbor["switch"] or neighbor["port"]:
                return new_scan_result(
                    selected,
                    timeout_seconds,
                    protocol=neighbor["protocol"],
                    switch=neighbor["switch"],
                    port=neighbor["port"],
                    status="success",
                )

        return result
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
