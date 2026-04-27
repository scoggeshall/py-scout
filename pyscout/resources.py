from __future__ import annotations

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        base_path = Path(getattr(sys, "_MEIPASS"))
    else:
        base_path = Path(__file__).resolve().parent.parent

    return base_path.joinpath(*parts)


def app_icon_path() -> Path:
    return resource_path("assets", "pyscout-taskbar-icon.png")


def app_logo_path() -> Path:
    return resource_path("assets", "pyscout-logo.png")
