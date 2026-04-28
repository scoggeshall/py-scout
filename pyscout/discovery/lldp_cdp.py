from __future__ import annotations

from threading import Event
from typing import Any

from pyscout.discovery.adapters import CaptureAdapter
from pyscout.discovery.backends import DiscoveryProtocol
from pyscout.discovery.backends import ScapyDiscoveryBackend


def discover_lldp_cdp(
    adapter: CaptureAdapter,
    timeout_seconds: int = 90,
    *,
    protocol: DiscoveryProtocol = "both",
    sniff_function: Any | None = None,
    cancel_event: Event | None = None,
) -> dict[str, str]:
    return ScapyDiscoveryBackend(
        sniff_function=sniff_function,
        protocol=protocol,
        cancel_event=cancel_event,
    ).discover(
        adapter,
        timeout_seconds,
    )
