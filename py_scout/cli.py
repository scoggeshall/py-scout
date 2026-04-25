from __future__ import annotations

import argparse
import sys
from typing import Sequence

from .scanner import (
    ScannerError,
    ScanResult,
    get_interface_inventory,
    resolve_capture_interface,
    scan_on_interface,
)


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
    return parser


def print_interface_list() -> None:
    interfaces = get_interface_inventory()

    print("Available tshark capture interfaces:")
    for iface in interfaces:
        print(f"{iface.number:>4}  {iface.name:<35} {iface.status:<12} {iface.role}")


def print_human_result(result: ScanResult) -> None:
    if result.status == "success":
        print("Connected switchport found")
        print("--------------------------")
        print(f"Protocol : {result.protocol or 'unknown'}")
        print(f"Switch   : {result.switch or 'unknown'}")
        print(f"Port     : {result.port or 'unknown'}")
        return

    print("No LLDP/CDP neighbor detected (timeout reached).")


def run_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.list:
            print_interface_list()
            return 0

        selected = resolve_capture_interface(args.interface)

        print(f"Using adapter: {selected.name}")
        print(f"Using tshark interface: {selected.number}")
        print(f"Waiting up to {args.timeout} seconds for LLDP/CDP...\n", flush=True)

        result = scan_on_interface(selected, args.timeout)
        print_human_result(result)
        return 0
    except ScannerError as exc:
        print(str(exc))
        return 1
    except KeyboardInterrupt:
        print("\nStopped.")
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    return run_cli(argv)


if __name__ == "__main__":
    sys.exit(main())
