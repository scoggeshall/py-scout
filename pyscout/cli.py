from __future__ import annotations

import argparse
from typing import Sequence

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyscout",
        description=(
            "Py-Scout is a GUI-first switchport discovery and physical mapping tool. "
            "Scapy packet capture on Windows requires Npcap."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("version", help="Print the Py-Scout version and exit.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(f"pyscout {__version__}")
        return 0

    parser.print_help()
    return 0


__all__ = ["build_parser", "main"]
