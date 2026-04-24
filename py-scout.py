import argparse
import json
import re
import subprocess
import sys
import time
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


def run_cmd(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


def is_bad_interface(name: str) -> bool:
    lowered = name.lower()
    return any(word in lowered for word in BAD_INTERFACE_WORDS)


def get_tshark_interfaces() -> list[dict[str, str]]:
    result = run_cmd(["tshark", "-D"])

    if result.returncode != 0:
        print("ERROR: tshark not found or not working.")
        print(result.stderr.strip())
        sys.exit(1)

    interfaces: list[dict[str, str]] = []

    for line in result.stdout.splitlines():
        match = re.match(r"^(\d+)\.\s+(.+?)\s+\((.+)\)$", line.strip())
        if match:
            number, device, name = match.groups()
            interfaces.append(
                {
                    "number": number.strip(),
                    "device": device.strip(),
                    "name": name.strip(),
                    "raw": line.strip(),
                }
            )

    return interfaces


def get_windows_adapters() -> dict[str, dict[str, Any]]:
    ps = (
        "Get-NetAdapter | "
        "Select-Object Name,InterfaceDescription,Status,MacAddress,LinkSpeed | "
        "ConvertTo-Json -Compress"
    )

    result = run_cmd(["powershell", "-NoProfile", "-Command", ps])

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


def auto_select_tshark_interface() -> tuple[str | None, str | None]:
    interfaces = get_tshark_interfaces()
    adapters = get_windows_adapters()

    ethernet_candidates = [
        iface for iface in interfaces
        if "ethernet" in iface["name"].lower() and not is_bad_interface(iface["name"])
    ]

    if not ethernet_candidates:
        return None, None

    up_candidates = [
        iface for iface in ethernet_candidates
        if is_adapter_up(iface["name"], adapters)
    ]

    if up_candidates:
        return up_candidates[0]["number"], up_candidates[0]["name"]

    # Fallback: tshark sees Ethernet adapters, but Windows status lookup failed.
    # Use the first sane Ethernet capture interface rather than failing.
    return ethernet_candidates[0]["number"], ethernet_candidates[0]["name"]


def get_tshark_interface_number(adapter_name: str) -> str | None:
    interfaces = get_tshark_interfaces()

    for iface in interfaces:
        if iface["name"].lower() == adapter_name.lower():
            return iface["number"]

    return None


def list_interfaces() -> None:
    interfaces = get_tshark_interfaces()
    adapters = get_windows_adapters()

    print("Available tshark capture interfaces:")
    for iface in interfaces:
        name = iface["name"]
        adapter = adapters.get(name.lower())
        status = adapter.get("Status", "unknown") if adapter else "unknown"

        if is_bad_interface(name):
            role = "skip"
        elif "ethernet" in name.lower() and str(status).lower() == "up":
            role = "candidate/up"
        elif "ethernet" in name.lower():
            role = "candidate/down"
        else:
            role = "skip"

        print(f"{iface['number']:>4}  {name:<35} {str(status):<12} {role}")


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
        port_match = re.search(r"\bIN/([A-Za-z]+\d+/\d+/\d+)", line)

        if sys_match:
            result["switch"] = sys_match.group(1)

        if port_match:
            result["port"] = port_match.group(1)

    elif "CDP" in line:
        result["protocol"] = "CDP"

        sys_match = re.search(r"Device ID:\s+(.+?)\s+Port ID:", line)
        port_match = re.search(r"Port ID:\s+([A-Za-z]+\S+)", line)

        if sys_match:
            result["switch"] = sys_match.group(1).strip()

        if port_match:
            result["port"] = port_match.group(1).strip()

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Identify connected switch and port using LLDP/CDP via tshark."
    )
    parser.add_argument(
        "-i",
        "--interface",
        help='Optional Windows adapter name, example: "Ethernet"',
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=90,
        help="Seconds to wait before giving up",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available capture interfaces and exit",
    )

    args = parser.parse_args()

    if args.list:
        list_interfaces()
        return

    if args.interface:
        adapter_name = args.interface
        iface_num = get_tshark_interface_number(adapter_name)

        if not iface_num:
            print(f"ERROR: Could not map Windows adapter '{adapter_name}' to tshark interface.")
            print("Run: py .\\identify-port.py --list")
            sys.exit(1)
    else:
        iface_num, adapter_name = auto_select_tshark_interface()

        if not iface_num or not adapter_name:
            print("ERROR: Could not auto-select an active Ethernet capture interface.")
            print("Run: py .\\identify-port.py --list")
            sys.exit(1)

    print(f"Using adapter: {adapter_name}")
    print(f"Using tshark interface: {iface_num}")
    print(f"Waiting up to {args.timeout} seconds for LLDP/CDP...\n")

    cmd = [
        "tshark",
        "-i", str(iface_num),
        "-l",
        "-Y", "lldp or cdp",
    ]

    start = time.time()

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    try:
        assert proc.stdout is not None

        while time.time() - start < args.timeout:
            line = proc.stdout.readline()

            if not line:
                time.sleep(0.2)
                continue

            neighbor = parse_neighbor(line)

            if neighbor["switch"] or neighbor["port"]:
                print("Connected switchport found")
                print("--------------------------")
                print(f"Protocol : {neighbor['protocol']}")
                print(f"Switch   : {neighbor['switch'] or 'unknown'}")
                print(f"Port     : {neighbor['port'] or 'unknown'}")
                return

        print("No LLDP/CDP neighbor detected.")
        print("Likely causes: LLDP/CDP disabled, wrong adapter, dock/phone filtering, or no switch advertisement.")

    except KeyboardInterrupt:
        print("\nStopped.")

    finally:
        proc.terminate()

if __name__ == "__main__":
    main()
