from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from pyscout.discovery.adapters import CaptureAdapter


DiscoveryProtocol = Literal["both", "lldp", "cdp"]


class DiscoveryBackend(Protocol):
    name: str
    display_name: str

    def discover(
        self,
        adapter: CaptureAdapter,
        timeout_seconds: int,
    ) -> dict[str, str]:
        """Discover LLDP/CDP neighbor details for the selected adapter."""


def success_result(
    adapter: CaptureAdapter,
    parsed: dict[str, str],
    *,
    backend: str,
) -> dict[str, str]:
    result = {
        "local_adapter": adapter.name,
        "switch_name": parsed.get("switch_name", ""),
        "switch_port": parsed.get("switch_port", ""),
        "neighbor_ip": parsed.get("neighbor_ip", ""),
        "protocol": parsed.get("protocol", ""),
        "timestamp": _timestamp(),
        "backend": backend,
        "status": "success",
        "error": "",
    }
    for field_name in (
        "system_name",
        "device_id",
        "port_id",
        "management_ip",
        "platform",
        "software_version",
        "capabilities",
    ):
        value = parsed.get(field_name, "")
        if value:
            result[field_name] = value
    return result


def timeout_result(
    adapter: CaptureAdapter,
    timeout_seconds: int,
    *,
    backend: str,
    message: str | None = None,
) -> dict[str, str]:
    return {
        "local_adapter": adapter.name,
        "switch_name": "",
        "switch_port": "",
        "neighbor_ip": "",
        "protocol": "",
        "timestamp": _timestamp(),
        "backend": backend,
        "status": "timeout",
        "error": message or "No LLDP/CDP packets received before timeout.",
    }


def error_result(
    adapter: CaptureAdapter,
    message: str,
    *,
    backend: str,
) -> dict[str, str]:
    return {
        "local_adapter": adapter.name,
        "switch_name": "",
        "switch_port": "",
        "neighbor_ip": "",
        "protocol": "",
        "timestamp": _timestamp(),
        "backend": backend,
        "status": "error",
        "error": message,
    }


def unavailable_result(
    adapter: CaptureAdapter,
    message: str,
    *,
    backend: str,
) -> dict[str, str]:
    result = error_result(adapter, message, backend=backend)
    result["status"] = "unavailable"
    return result


def canceled_result(
    adapter: CaptureAdapter,
    *,
    backend: str,
) -> dict[str, str]:
    result = error_result(adapter, "Discovery canceled.", backend=backend)
    result["status"] = "canceled"
    return result


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
