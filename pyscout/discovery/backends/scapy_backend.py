from __future__ import annotations

import importlib
import ipaddress
import time
from threading import Event
from typing import Any

from pyscout.discovery.adapters import CaptureAdapter
from pyscout.discovery.backends.base import DiscoveryProtocol
from pyscout.discovery.backends.base import canceled_result
from pyscout.discovery.backends.base import error_result, success_result, timeout_result
from pyscout.discovery.backends.base import unavailable_result


LLDP_ETHERTYPE = 0x88CC
LLDP_TLV_TYPE_END = 0
LLDP_TLV_TYPE_PORT_ID = 2
LLDP_TLV_TYPE_PORT_DESCRIPTION = 4
LLDP_TLV_TYPE_SYSTEM_NAME = 5
LLDP_TLV_TYPE_MANAGEMENT_ADDRESS = 8
LLDP_ADDRESS_SUBTYPE_IPV4 = 1

CDP_DESTINATION_MAC = bytes.fromhex("01000ccccccc")
CDP_SNAP_HEADER = bytes.fromhex("aaaa0300000c2000")
CDP_HEADER_LENGTH = 4
CDP_TLV_TYPE_DEVICE_ID = 0x0001
CDP_TLV_TYPE_ADDRESS = 0x0002
CDP_TLV_TYPE_PORT_ID = 0x0003
CDP_TLV_TYPE_CAPABILITIES = 0x0004
CDP_TLV_TYPE_SOFTWARE_VERSION = 0x0005
CDP_TLV_TYPE_PLATFORM = 0x0006
CDP_PROTOCOL_TYPE_NLPID = 1
CDP_PROTOCOL_TYPE_802_2 = 2
CDP_NLPID_IPV4 = b"\xcc"
CDP_ETHERTYPE_IPV4 = b"\x08\x00"

DISCOVERY_CAPTURE_FILTER = "ether proto 0x88cc or ether dst 01:00:0c:cc:cc:cc"
LLDP_CAPTURE_FILTER = "ether proto 0x88cc"
CDP_CAPTURE_FILTER = "ether dst 01:00:0c:cc:cc:cc"
NPCAP_REQUIRED_MESSAGE = "Packet capture requires Npcap on Windows."


class ScapyDiscoveryBackend:
    name = "scapy"
    display_name = "scapy"

    def __init__(
        self,
        *,
        sniff_function: Any | None = None,
        protocol: DiscoveryProtocol = "both",
        cancel_event: Event | None = None,
    ) -> None:
        self.sniff_function = sniff_function
        self.protocol = normalize_discovery_protocol(protocol)
        self.cancel_event = cancel_event

    def discover(
        self,
        adapter: CaptureAdapter,
        timeout_seconds: int,
    ) -> dict[str, str]:
        if self._is_canceled():
            return canceled_result(adapter, backend=self.display_name)

        sniff_function = self.sniff_function
        if sniff_function is None:
            try:
                sniff_function = importlib.import_module("scapy.all").sniff
            except ImportError:
                return unavailable_result(
                    adapter,
                    "Scapy is not installed.",
                    backend=self.display_name,
                )

        parsed_packets: list[dict[str, str]] = []

        def handle_packet(packet: object) -> None:
            frame = bytes(packet)
            parsed = parse_discovery_frame(frame, protocol=self.protocol)
            if parsed:
                parsed_packets.append(parsed)

        try:
            deadline = time.monotonic() + max(timeout_seconds, 0)
            while not parsed_packets and not self._is_canceled():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                started_at = time.monotonic()
                sniff_function(
                    iface=adapter.scapy_name,
                    filter=capture_filter_for_protocol(self.protocol),
                    prn=handle_packet,
                    stop_filter=lambda _packet: bool(parsed_packets)
                    or self._is_canceled(),
                    store=False,
                    timeout=min(1.0, remaining),
                )
                if (
                    not parsed_packets
                    and not self._is_canceled()
                    and time.monotonic() - started_at < 0.01
                ):
                    time.sleep(0.01)
        except ImportError:
            return unavailable_result(
                adapter,
                "Scapy is not installed.",
                backend=self.display_name,
            )
        except PermissionError:
            return error_result(
                adapter,
                "Missing permission to capture packets.",
                backend=self.display_name,
            )
        except Exception as exc:
            if _is_capture_dependency_error(exc):
                return error_result(
                    adapter,
                    NPCAP_REQUIRED_MESSAGE,
                    backend=self.display_name,
                )
            if _is_permission_error(exc):
                return error_result(
                    adapter,
                    "Missing permission to capture packets.",
                    backend=self.display_name,
                )
            return error_result(
                adapter,
                f"Unable to start Scapy packet capture: {_clean_exception_message(exc)}",
                backend=self.display_name,
            )

        if parsed_packets:
            return success_result(adapter, parsed_packets[0], backend=self.display_name)

        if self._is_canceled():
            return canceled_result(adapter, backend=self.display_name)

        return timeout_result(adapter, timeout_seconds, backend=self.display_name)

    def _is_canceled(self) -> bool:
        return bool(self.cancel_event and self.cancel_event.is_set())


def normalize_discovery_protocol(protocol: str) -> DiscoveryProtocol:
    return protocol if protocol in {"both", "lldp", "cdp"} else "both"


def capture_filter_for_protocol(protocol: DiscoveryProtocol) -> str:
    if protocol == "lldp":
        return LLDP_CAPTURE_FILTER
    if protocol == "cdp":
        return CDP_CAPTURE_FILTER
    return DISCOVERY_CAPTURE_FILTER


def parse_discovery_frame(
    frame: bytes,
    *,
    protocol: DiscoveryProtocol = "both",
) -> dict[str, str] | None:
    normalized_protocol = normalize_discovery_protocol(protocol)
    if normalized_protocol in {"both", "lldp"} and is_lldp_frame(frame):
        return parse_lldp_frame(frame)

    if normalized_protocol in {"both", "cdp"} and is_cdp_frame(frame):
        return parse_cdp_frame(frame)

    return None


def is_lldp_frame(frame: bytes) -> bool:
    if len(frame) < 14:
        return False

    return int.from_bytes(frame[12:14], "big") == LLDP_ETHERTYPE


def is_cdp_frame(frame: bytes) -> bool:
    if len(frame) < 14 + len(CDP_SNAP_HEADER):
        return False

    return frame[:6] == CDP_DESTINATION_MAC and frame[14:22] == CDP_SNAP_HEADER


def parse_lldp_frame(frame: bytes) -> dict[str, str] | None:
    if not is_lldp_frame(frame):
        return None

    return parse_lldp_tlvs(frame[14:])


def parse_lldp_tlvs(payload: bytes) -> dict[str, str] | None:
    offset = 0
    port_id = ""
    port_description = ""
    system_name = ""
    management_address = ""

    while offset + 2 <= len(payload):
        header = int.from_bytes(payload[offset : offset + 2], "big")
        offset += 2
        tlv_type = header >> 9
        tlv_length = header & 0x01FF
        if offset + tlv_length > len(payload):
            break
        value = payload[offset : offset + tlv_length]
        offset += tlv_length

        if tlv_type == LLDP_TLV_TYPE_END:
            break

        if tlv_type == LLDP_TLV_TYPE_PORT_ID:
            port_id = _parse_lldp_port_id(value)
        elif tlv_type == LLDP_TLV_TYPE_PORT_DESCRIPTION:
            port_description = _decode_text(value)
        elif tlv_type == LLDP_TLV_TYPE_SYSTEM_NAME:
            system_name = _decode_text(value)
        elif tlv_type == LLDP_TLV_TYPE_MANAGEMENT_ADDRESS:
            management_address = _parse_lldp_management_address(value)

    if not any((port_id, port_description, system_name, management_address)):
        return None

    return {
        "protocol": "LLDP",
        "switch_name": system_name,
        "switch_port": port_description or port_id,
        "neighbor_ip": management_address,
        "system_name": system_name,
        "port_id": port_description or port_id,
        "management_ip": management_address,
    }


def parse_cdp_frame(frame: bytes) -> dict[str, str] | None:
    if not is_cdp_frame(frame):
        return None

    return parse_cdp_tlvs(frame[14 + len(CDP_SNAP_HEADER) :])


def parse_cdp_tlvs(payload: bytes) -> dict[str, str] | None:
    if len(payload) < CDP_HEADER_LENGTH:
        return None

    offset = CDP_HEADER_LENGTH
    device_id = ""
    port_id = ""
    management_address = ""
    capabilities = ""
    platform = ""
    software_version = ""

    while offset + 4 <= len(payload):
        tlv_type = int.from_bytes(payload[offset : offset + 2], "big")
        tlv_length = int.from_bytes(payload[offset + 2 : offset + 4], "big")
        if tlv_length < 4 or offset + tlv_length > len(payload):
            break

        value = payload[offset + 4 : offset + tlv_length]
        offset += tlv_length

        if tlv_type == CDP_TLV_TYPE_DEVICE_ID:
            device_id = _decode_text(value)
        elif tlv_type == CDP_TLV_TYPE_ADDRESS:
            management_address = _parse_cdp_address_tlv(value)
        elif tlv_type == CDP_TLV_TYPE_PORT_ID:
            port_id = _decode_text(value)
        elif tlv_type == CDP_TLV_TYPE_CAPABILITIES:
            capabilities = _parse_cdp_capabilities(value)
        elif tlv_type == CDP_TLV_TYPE_PLATFORM:
            platform = _decode_text(value)
        elif tlv_type == CDP_TLV_TYPE_SOFTWARE_VERSION:
            software_version = _first_line(value)

    if not any(
        (device_id, port_id, management_address, capabilities, platform, software_version)
    ):
        return None

    return {
        "protocol": "CDP",
        "switch_name": device_id,
        "switch_port": port_id,
        "neighbor_ip": management_address,
        "device_id": device_id,
        "port_id": port_id,
        "management_ip": management_address,
        "capabilities": capabilities,
        "platform": platform,
        "software_version": software_version,
    }


def _parse_lldp_port_id(value: bytes) -> str:
    if len(value) < 2:
        return ""

    subtype = value[0]
    port_id = value[1:]
    if subtype in {1, 5, 7}:
        return _decode_text(port_id)

    if subtype == 3 and len(port_id) == 6:
        return _format_mac_address(port_id)

    if subtype == 2:
        return _decode_best_effort_or_hex(port_id)

    return _decode_best_effort_or_hex(port_id)


def _parse_lldp_management_address(value: bytes) -> str:
    if len(value) < 2:
        return ""

    address_length = value[0]
    address_end = 1 + address_length
    if address_length < 2 or len(value) < address_end:
        return ""

    address_subtype = value[1]
    address = value[2:address_end]
    if address_subtype == LLDP_ADDRESS_SUBTYPE_IPV4 and len(address) == 4:
        return str(ipaddress.IPv4Address(address))

    return ""


def _parse_cdp_address_tlv(value: bytes) -> str:
    if len(value) < 4:
        return ""

    address_count = int.from_bytes(value[:4], "big")
    offset = 4
    for _index in range(address_count):
        if offset + 2 > len(value):
            return ""

        protocol_type = value[offset]
        protocol_length = value[offset + 1]
        offset += 2
        if offset + protocol_length > len(value):
            return ""
        protocol = value[offset : offset + protocol_length]
        offset += protocol_length

        if offset + 2 > len(value):
            return ""
        address_length = int.from_bytes(value[offset : offset + 2], "big")
        offset += 2
        if offset + address_length > len(value):
            return ""
        address = value[offset : offset + address_length]
        offset += address_length

        if _is_cdp_ipv4_protocol(protocol_type, protocol) and address_length == 4:
            return str(ipaddress.IPv4Address(address))

    return ""


def _parse_cdp_capabilities(value: bytes) -> str:
    if len(value) != 4:
        return ""

    return f"0x{int.from_bytes(value, 'big'):08x}"


def _is_cdp_ipv4_protocol(protocol_type: int, protocol: bytes) -> bool:
    if protocol_type == CDP_PROTOCOL_TYPE_NLPID and protocol == CDP_NLPID_IPV4:
        return True

    return protocol_type == CDP_PROTOCOL_TYPE_802_2 and protocol == CDP_ETHERTYPE_IPV4


def _decode_text(value: bytes) -> str:
    return value.decode("utf-8", errors="replace").strip("\x00\r\n\t ")


def _decode_best_effort_or_hex(value: bytes) -> str:
    decoded = _decode_text(value)
    if (
        decoded
        and "\ufffd" not in decoded
        and all(char.isprintable() for char in decoded)
    ):
        return decoded

    return value.hex(":")


def _format_mac_address(value: bytes) -> str:
    return ":".join(f"{byte:02x}" for byte in value)


def _first_line(value: bytes) -> str:
    lines = _decode_text(value).splitlines()
    return lines[0].strip() if lines else ""


def _clean_exception_message(exc: Exception) -> str:
    return str(exc).strip() or exc.__class__.__name__


def _is_permission_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "permission" in message or "access denied" in message


def _is_capture_dependency_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        phrase in message
        for phrase in (
            "npcap",
            "winpcap",
            "libpcap",
            "no pcap",
            "pcap is not available",
            "cannot set filter",
        )
    )
