from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Sequence

from .scanner import (
    ScannerError,
    ScanResult,
    get_interface_inventory,
    resolve_capture_interface,
    scan_on_interface,
)


CSV_LOG_FIELDS = [
    "timestamp",
    "adapter_name",
    "tshark_interface_number",
    "protocol",
    "switch",
    "port",
    "status",
    "timeout_seconds",
]


def build_parser() -> argparse.ArgumentParser:
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
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of human-readable output",
    )
    parser.add_argument(
        "--log-csv",
        action="store_true",
        help="Append scan results to a CSV log file",
    )
    parser.add_argument(
        "--log-json",
        action="store_true",
        help="Append scan results to a JSON log file",
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory for optional log files",
    )
    return parser


def print_json_output(payload: object) -> None:
    print(json.dumps(payload, indent=2))


def print_interface_list(json_mode: bool) -> None:
    interfaces = get_interface_inventory()

    if json_mode:
        print_json_output(
            [
                {
                    "number": iface.number,
                    "name": iface.name,
                    "status": iface.status,
                    "role": iface.role,
                }
                for iface in interfaces
            ]
        )
        return

    print("Available tshark capture interfaces:")
    for iface in interfaces:
        print(f"{iface.number:>4}  {iface.name:<35} {iface.status:<12} {iface.role}")


def print_scan_result(result: ScanResult, json_mode: bool) -> None:
    if json_mode:
        print_json_output(result.to_dict())
        return

    if result.status == "success":
        print("Connected switchport found")
        print("--------------------------")
        print(f"Protocol : {result.protocol or 'unknown'}")
        print(f"Switch   : {result.switch or 'unknown'}")
        print(f"Port     : {result.port or 'unknown'}")
        return

    print("No LLDP/CDP neighbor detected (timeout reached).")


def ensure_log_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def append_csv_log(path: Path, result: ScanResult) -> None:
    record = result.to_dict()
    file_exists = path.exists()

    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_LOG_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({field: record.get(field) for field in CSV_LOG_FIELDS})


def append_json_log(path: Path, result: ScanResult) -> None:
    record = result.to_dict()

    if path.exists():
        try:
            existing_data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_data = []
    else:
        existing_data = []

    if not isinstance(existing_data, list):
        existing_data = []

    existing_data.append({field: record.get(field) for field in CSV_LOG_FIELDS})
    path.write_text(json.dumps(existing_data, indent=2), encoding="utf-8")


def write_logs(args: argparse.Namespace, result: ScanResult) -> None:
    if not args.log_csv and not args.log_json:
        return

    log_dir = Path(args.log_dir)
    ensure_log_dir(log_dir)

    if args.log_csv:
        append_csv_log(log_dir / "py-scout-log.csv", result)

    if args.log_json:
        append_json_log(log_dir / "py-scout-log.json", result)


def run_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.list:
            print_interface_list(args.json)
            return 0

        selected = resolve_capture_interface(args.interface)

        if not args.json:
            print(f"Using adapter: {selected.name}")
            print(f"Using tshark interface: {selected.number}")
            print(f"Waiting up to {args.timeout} seconds for LLDP/CDP...\n", flush=True)

        result = scan_on_interface(selected, args.timeout)
        write_logs(args, result)
        print_scan_result(result, args.json)
        return 0
    except ScannerError as exc:
        if args.json:
            print_json_output({"status": "error", "error": str(exc)})
        else:
            print(str(exc))
        return 1
    except KeyboardInterrupt:
        if args.json:
            print_json_output({"status": "stopped"})
        else:
            print("\nStopped.")
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    return run_cli(argv)


if __name__ == "__main__":
    sys.exit(main())
