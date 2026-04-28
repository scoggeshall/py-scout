from __future__ import annotations

import json
import importlib
import subprocess
from dataclasses import dataclass
from typing import Any


BAD_ADAPTER_WORDS = (
    "bluetooth",
    "loopback",
    "miniport",
    "pangp",
    "virtual",
    "wi-fi direct",
    "hyper-v",
    "vmware",
    "virtualbox",
    "teredo",
    "isatap",
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
    capture_name: str = ""
    description: str = ""
    guid: str = ""
    is_loopback: bool = False
    is_up: bool | None = None
    status_text: str = ""
    status: str = "unknown"
    confidence: int = 0
    reason: str = ""

    @property
    def display_name(self) -> str:
        label = self.name or self.description or self.capture_name or self.device
        if self.description and self.description.lower() != label.lower():
            label = f"{label} - {self.description}"

        status = self.status_text or self.status
        return f"{label} ({status})" if status else label

    @property
    def scapy_name(self) -> str:
        return self.capture_name or self.device or self.name


def list_capture_adapters() -> list[CaptureAdapter]:
    windows_adapters = _get_windows_adapters()
    return sorted(
        _get_scapy_adapters(windows_adapters),
        key=lambda adapter: adapter.confidence,
        reverse=True,
    )


def _get_scapy_adapters(
    windows_adapters: dict[str, dict[str, Any]] | None = None,
) -> list[CaptureAdapter]:
    try:
        scapy_all = importlib.import_module("scapy.all")
    except ImportError as exc:
        raise AdapterDiscoveryError("Scapy is not installed.") from exc

    windows_adapters = windows_adapters or {}
    adapters = _get_scapy_conf_adapters(scapy_all, windows_adapters)
    if adapters:
        return adapters

    return _get_scapy_fallback_adapters(scapy_all, windows_adapters)


def _get_scapy_conf_adapters(
    scapy_all: Any,
    windows_adapters: dict[str, dict[str, Any]],
) -> list[CaptureAdapter]:
    data = getattr(getattr(scapy_all.conf, "ifaces", None), "data", {})
    adapters: list[CaptureAdapter] = []
    for index, (key, iface) in enumerate(data.items(), start=1):
        capture_name = str(getattr(iface, "network_name", "") or key or "").strip()
        name = str(getattr(iface, "name", "") or "").strip()
        description = str(getattr(iface, "description", "") or "").strip()
        guid = str(getattr(iface, "guid", "") or "").strip()
        interface_type = getattr(iface, "type", None)
        raw = repr(iface)
        adapter = build_capture_adapter(
            index=index,
            capture_name=capture_name,
            name=name,
            description=description,
            guid=guid,
            raw=raw,
            interface_type=interface_type,
            windows_adapters=windows_adapters,
        )
        if adapter is not None:
            adapters.append(adapter)

    return adapters


def _get_scapy_fallback_adapters(
    scapy_all: Any,
    windows_adapters: dict[str, dict[str, Any]],
) -> list[CaptureAdapter]:
    try:
        get_windows_if_list = importlib.import_module(
            "scapy.arch.windows"
        ).get_windows_if_list
        windows_ifaces = get_windows_if_list()
    except (ImportError, AttributeError):
        windows_ifaces = []

    get_if_list = getattr(scapy_all, "get_if_list")
    capture_names = [str(name) for name in get_if_list()]
    capture_by_guid = {_guid_from_capture_name(name).lower(): name for name in capture_names}

    adapters: list[CaptureAdapter] = []
    for index, item in enumerate(windows_ifaces, start=1):
        name = str(item.get("name", "")).strip()
        description = str(item.get("description", "")).strip()
        guid = str(item.get("guid", "")).strip()
        capture_name = capture_by_guid.get(guid.lower()) or _capture_name_from_guid(guid)
        adapter = build_capture_adapter(
            index=index,
            capture_name=capture_name,
            name=name,
            description=description,
            guid=guid,
            raw=json.dumps(item, default=str),
            interface_type=item.get("type"),
            windows_adapters=windows_adapters,
        )
        if adapter is not None:
            adapters.append(adapter)

    if adapters:
        return adapters

    for index, capture_name in enumerate(capture_names, start=1):
        adapter = build_capture_adapter(
            index=index,
            capture_name=capture_name,
            name=capture_name,
            raw=capture_name,
            windows_adapters=windows_adapters,
        )
        if adapter is not None:
            adapters.append(adapter)

    return adapters


def build_capture_adapter(
    *,
    index: int,
    capture_name: str,
    name: str,
    raw: str = "",
    description: str = "",
    guid: str = "",
    interface_type: object | None = None,
    windows_adapters: dict[str, dict[str, Any]] | None = None,
) -> CaptureAdapter | None:
    capture_name = capture_name.strip()
    name = name.strip() or _friendly_name_from_capture_name(capture_name)
    description = description.strip()
    guid = guid.strip() or _guid_from_capture_name(capture_name)
    if not capture_name:
        return None

    windows_adapter = _match_windows_adapter(name, description, guid, windows_adapters or {})
    status = (
        str(windows_adapter.get("Status", "")).strip()
        if windows_adapter
        else _infer_status_from_raw(raw)
    )
    is_loopback = _is_loopback_adapter(
        name,
        description,
        capture_name,
        interface_type=interface_type,
    )
    if _should_skip_adapter(name, description, capture_name, is_loopback):
        return None

    is_up = _is_up_status(status)
    confidence, reason = classify_adapter(
        name=name,
        status=status,
        description=description,
        is_loopback=is_loopback,
        is_up=is_up,
    )
    return CaptureAdapter(
        number=str(index),
        device=capture_name,
        name=name,
        raw=raw or capture_name,
        capture_name=capture_name,
        description=description,
        guid=guid,
        is_loopback=is_loopback,
        is_up=is_up,
        status_text=_friendly_status_text(status, is_up),
        status=status or "unknown",
        confidence=confidence,
        reason=reason,
    )


def _match_windows_adapter(
    name: str,
    description: str,
    guid: str,
    windows_adapters: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    candidates = [name, description, guid]
    for candidate in candidates:
        key = candidate.strip().lower()
        if key and key in windows_adapters:
            return windows_adapters[key]

    return None


def _should_skip_adapter(
    name: str,
    description: str,
    capture_name: str,
    is_loopback: bool,
) -> bool:
    if is_loopback:
        return True

    text = f"{name} {description} {capture_name}".lower()
    return any(word in text for word in BAD_ADAPTER_WORDS)


def _is_loopback_adapter(
    name: str,
    description: str,
    capture_name: str,
    *,
    interface_type: object | None,
) -> bool:
    text = f"{name} {description} {capture_name}".lower()
    return "loopback" in text or "npf_loopback" in text or interface_type == 24


def _infer_status_from_raw(raw: str) -> str:
    lowered = raw.lower()
    if "disconnected" in lowered:
        return "disconnected"
    if "up" in lowered or "running" in lowered:
        return "up"
    return "unknown"


def _is_up_status(status: str) -> bool | None:
    lowered = status.lower()
    if not lowered or lowered == "unknown":
        return None
    if "disconnected" in lowered or "down" in lowered:
        return False
    if "up" in lowered or "connected" in lowered:
        return True
    return None


def _friendly_status_text(status: str, is_up: bool | None) -> str:
    if is_up is True:
        return "up"
    if is_up is False:
        return "down"
    return status.lower() if status else "unknown"


def _guid_from_capture_name(capture_name: str) -> str:
    value = capture_name.strip()
    marker = r"\Device\NPF_"
    if value.startswith(marker):
        return value[len(marker) :]
    return ""


def _capture_name_from_guid(guid: str) -> str:
    return rf"\Device\NPF_{guid}" if guid else ""


def _friendly_name_from_capture_name(capture_name: str) -> str:
    guid = _guid_from_capture_name(capture_name)
    return guid or capture_name


def _adapter_text(name: str, description: str) -> str:
    return f"{name} {description}".lower()


def _is_ethernet(name: str, description: str) -> bool:
    text = _adapter_text(name, description)
    return any(
        word in text
        for word in (
            "ethernet",
            "gbe",
            "gigabit",
            "realtek",
            "intel ethernet",
            "usb ethernet",
            "dell giga",
        )
    )


def _is_wifi(name: str, description: str) -> bool:
    text = _adapter_text(name, description)
    return "wi-fi" in text or "wifi" in text or "wireless" in text


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


def classify_adapter(
    name: str,
    status: str,
    *,
    description: str = "",
    is_loopback: bool = False,
    is_up: bool | None = None,
) -> tuple[int, str]:
    if is_loopback:
        return 0, "Skipped adapter type"

    if any(word in _adapter_text(name, description) for word in BAD_ADAPTER_WORDS):
        return 0, "Skipped adapter type"

    ethernet = _is_ethernet(name, description)
    wifi = _is_wifi(name, description)

    if ethernet and is_up is True:
        return 100, "Ethernet adapter is up"

    if ethernet:
        return 75, "Ethernet adapter"

    if is_up is True and not wifi:
        return 50, "Adapter is up"

    if wifi and is_up is True:
        return 40, "Wi-Fi adapter is up"

    if wifi:
        return 25, "Wi-Fi adapter"

    return 25, "Possible capture adapter"


def _get_windows_adapters() -> dict[str, dict[str, Any]]:
    ps_command = (
        "Get-NetAdapter | "
        "Select-Object Name,InterfaceDescription,InterfaceGuid,Status,MacAddress,LinkSpeed | "
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
        description = str(item.get("InterfaceDescription", "")).strip()
        if description:
            adapters[description.lower()] = item
        guid = str(item.get("InterfaceGuid", "")).strip()
        if guid:
            adapters[guid.lower()] = item
            adapters[f"{{{guid}}}".lower()] = item

    return adapters


def _run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    options: dict[str, int] = {}
    if CREATE_NO_WINDOW:
        options["creationflags"] = CREATE_NO_WINDOW

    return subprocess.run(args, capture_output=True, text=True, **options)
