from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Any


BAD_ADAPTER_WORDS = (
    "wi-fi",
    "wireless",
    "bluetooth",
    "loopback",
    "pangp",
    "virtual",
    "local area connection",
    "etw",
)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class AdapterDiscoveryError(RuntimeError):
    """Raised when capture adapters cannot be discovered or selected."""


@dataclass(frozen=True, slots=True)
class CaptureAdapter:
    number: str
    device: str
    name: str
    raw: str
    status: str = "unknown"
    confidence: int = 0
    reason: str = ""

    @property
    def display_name(self) -> str:
        return f"{self.number} - {self.name} ({self.reason})"


def list_capture_adapters() -> list[CaptureAdapter]:
    tshark_adapters = _get_tshark_adapters()
    windows_adapters = _get_windows_adapters()
    adapters: list[CaptureAdapter] = []

    for adapter in tshark_adapters:
        windows_adapter = windows_adapters.get(adapter.name.lower())
        status = (
            str(windows_adapter.get("Status", "unknown"))
            if windows_adapter
            else "unknown"
        )
        confidence, reason = classify_adapter(adapter.name, status)
        adapters.append(
            CaptureAdapter(
                number=adapter.number,
                device=adapter.device,
                name=adapter.name,
                raw=adapter.raw,
                status=status,
                confidence=confidence,
                reason=reason,
            )
        )

    return adapters


def auto_select_adapter(adapters: list[CaptureAdapter] | None = None) -> CaptureAdapter:
    candidates = adapters if adapters is not None else list_capture_adapters()
    ranked = sorted(candidates, key=lambda item: item.confidence, reverse=True)

    if not ranked or ranked[0].confidence <= 0:
        raise AdapterDiscoveryError("No usable capture adapter was found.")

    return ranked[0]


def resolve_adapter(selection: str) -> CaptureAdapter:
    value = selection.strip().lower()
    if not value:
        raise AdapterDiscoveryError("Adapter selection is required.")

    for adapter in list_capture_adapters():
        if value in {adapter.number.lower(), adapter.name.lower()}:
            return adapter

    raise AdapterDiscoveryError(f"Adapter not found: {selection}")


def classify_adapter(name: str, status: str) -> tuple[int, str]:
    lowered_name = name.lower()
    lowered_status = status.lower()

    if any(word in lowered_name for word in BAD_ADAPTER_WORDS):
        return 0, "Skipped adapter type"

    if "ethernet" in lowered_name and lowered_status == "up":
        return 100, "Ethernet adapter is up"

    if "ethernet" in lowered_name:
        return 75, "Ethernet adapter"

    if lowered_status == "up":
        return 50, "Adapter is up"

    return 25, "Possible capture adapter"


def _get_tshark_adapters() -> list[CaptureAdapter]:
    try:
        result = _run_command(["tshark", "-D"])
    except FileNotFoundError as exc:
        raise AdapterDiscoveryError("tshark was not found.") from exc

    if result.returncode != 0:
        detail = result.stderr.strip()
        message = "Unable to list tshark capture adapters."
        if detail:
            message = f"{message} {detail}"
        raise AdapterDiscoveryError(message)

    adapters: list[CaptureAdapter] = []
    for line in result.stdout.splitlines():
        match = re.match(r"^(\d+)\.\s+(.+?)(?:\s+\((.+)\))?$", line.strip())
        if not match:
            continue

        number, device, name = match.groups()
        adapter_name = (name or device).strip()
        adapters.append(
            CaptureAdapter(
                number=number.strip(),
                device=device.strip(),
                name=adapter_name,
                raw=line.strip(),
            )
        )

    return adapters


def _get_windows_adapters() -> dict[str, dict[str, Any]]:
    ps_command = (
        "Get-NetAdapter | "
        "Select-Object Name,InterfaceDescription,Status,MacAddress,LinkSpeed | "
        "ConvertTo-Json -Compress"
    )

    try:
        result = _run_command(["powershell", "-NoProfile", "-Command", ps_command])
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


def _run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    options: dict[str, int] = {}
    if CREATE_NO_WINDOW:
        options["creationflags"] = CREATE_NO_WINDOW

    return subprocess.run(args, capture_output=True, text=True, **options)
