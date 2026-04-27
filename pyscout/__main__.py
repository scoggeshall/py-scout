from __future__ import annotations

import sys
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)

    if getattr(sys, "frozen", False) or not raw_args:
        from .gui.app import launch_gui

        return launch_gui()

    from .cli import main as cli_main

    return cli_main(raw_args)


if __name__ == "__main__":
    sys.exit(main())
