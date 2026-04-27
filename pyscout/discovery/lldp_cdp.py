from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from .adapters import CREATE_NO_WINDOW, CaptureAdapter


IPV4_PATTERN = (
    r"(?P<ip>"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}"
    r")"
)
MANAGEMENT_IP_PATTERNS = [
    re.compile(
        rf"\b(?:management|mgmt)\s+(?:address|addr|ip)\s*(?:=|:)?\s*"
        rf"(?:IPv4\s*)?{IPV4_PATTERN}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bIPv4\s+(?:management\s+)?address\s*(?:=|:)?\s*{IPV4_PATTERN}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bIP\s+address\s*(?:=|:)?\s*(?:IPv4\s*)?{IPV4_PATTERN}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bAddresses\s*(?:=|:)?\s*(?:IPv4\s*)?(?:address\s*)?{IPV4_PATTERN}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bMA\s*(?:=|:)\s*(?:IPv4\s*)?{IPV4_PATTERN}",
        re.IGNORECASE,
    ),
]


def discover_lldp_cdp(
    adapter: CaptureAdapter,
    timeout_seconds: int = 90,
    *,
    popen_factory: Any = subprocess.Popen,
) -> dict[str, str]:
    command = [
        "tshark",
        "-i",
        str(adapter.number),
        "-a",
        f"duration:{timeout_seconds}",
        "-l",
        "-Y",
        "lldp or cdp",
    ]
    options: dict[str, int] = {}
    if CREATE_NO_WINDOW:
        options["creationflags"] = CREATE_NO_WINDOW

    try:
        process = popen_factory(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **options,
        )
    except FileNotFoundError:
        return error_result(adapter, "tshark was not found.")
    except PermissionError:
        return error_result(adapter, "Missing permission to capture packets.")
    except OSError as exc:
        return error_result(adapter, f"Unable to start packet capture: {exc}")

    try:
        assert process.stdout is not None
        for line in process.stdout:
            parsed = parse_lldp_cdp_packet(line)
            if parsed:
                _stop_process(process)
                return discovery_result(adapter, parsed, status="success")

        return_code = process.wait()
        stderr = process.stderr.read() if process.stderr is not None else ""
        if return_code not in (0, None):
            return error_result(adapter, _capture_error_message(stderr))

        return timeout_result(adapter, timeout_seconds)
    finally:
        _stop_process(process)


def discover_from_lines(
    adapter: CaptureAdapter,
    lines: Iterable[str],
    timeout_seconds: int = 90,
) -> dict[str, str]:
    for line in lines:
        parsed = parse_lldp_cdp_packet(line)
        if parsed:
            return discovery_result(adapter, parsed, status="success")

    return timeout_result(adapter, timeout_seconds)


def parse_lldp_cdp_packet(packet_text: str) -> dict[str, str] | None:
    text = packet_text.strip()
    if not text:
        return None

    if "LLDP" in text:
        return _parse_lldp(text)

    if "CDP" in text:
        return _parse_cdp(text)

    return None


def discovery_result(
    adapter: CaptureAdapter,
    parsed: dict[str, str],
    *,
    status: str,
) -> dict[str, str]:
    return {
        "local_adapter": adapter.name,
        "switch_name": parsed.get("switch_name", ""),
        "switch_port": parsed.get("switch_port", ""),
        "neighbor_ip": parsed.get("neighbor_ip", ""),
        "protocol": parsed.get("protocol", ""),
        "timestamp": _timestamp(),
        "status": status,
        "error": "",
    }


def timeout_result(adapter: CaptureAdapter, timeout_seconds: int) -> dict[str, str]:
    return {
        "local_adapter": adapter.name,
        "switch_name": "",
        "switch_port": "",
        "neighbor_ip": "",
        "protocol": "",
        "timestamp": _timestamp(),
        "status": "timeout",
        "error": f"No LLDP/CDP packet found within {timeout_seconds} seconds.",
    }


def error_result(adapter: CaptureAdapter, message: str) -> dict[str, str]:
    return {
        "local_adapter": adapter.name,
        "switch_name": "",
        "switch_port": "",
        "neighbor_ip": "",
        "protocol": "",
        "timestamp": _timestamp(),
        "status": "error",
        "error": message,
    }


def _parse_lldp(text: str) -> dict[str, str]:
    switch_match = re.search(r"\bSysN=([^\s,]+)", text)
    if not switch_match:
        switch_match = re.search(
            r"\bSystem Name\s*(?:=|:)\s*([^,\n]+)",
            text,
            re.IGNORECASE,
        )

    port_match = re.search(r"\bIN/([^\s,]+)", text)
    if not port_match:
        port_match = re.search(
            r"\bPort (?:ID|Description)\s*(?:=|:)\s*([^,\n]+)",
            text,
            re.IGNORECASE,
        )

    return {
        "protocol": "LLDP",
        "switch_name": _match_text(switch_match),
        "switch_port": _match_text(port_match),
        "neighbor_ip": _parse_neighbor_ip(text),
    }


def _parse_cdp(text: str) -> dict[str, str]:
    switch_match = re.search(r"Device ID:\s+(.+?)\s+Port ID:", text, re.IGNORECASE)
    if not switch_match:
        switch_match = re.search(
            r"\bDevice ID\s*(?:=|:)\s*([^,\n]+)",
            text,
            re.IGNORECASE,
        )

    port_match = re.search(r"Port ID:\s+([^\s,]+)", text, re.IGNORECASE)
    if not port_match:
        port_match = re.search(
            r"\bPort ID\s*(?:=|:)\s*([^,\n]+)",
            text,
            re.IGNORECASE,
        )

    return {
        "protocol": "CDP",
        "switch_name": _match_text(switch_match),
        "switch_port": _match_text(port_match),
        "neighbor_ip": _parse_neighbor_ip(text),
    }


def _parse_neighbor_ip(text: str) -> str:
    for pattern in MANAGEMENT_IP_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group("ip")

    return ""


def _capture_error_message(stderr: str) -> str:
    lowered = stderr.lower()
    if "permission" in lowered or "access denied" in lowered:
        return "Missing permission to capture packets."

    if stderr.strip():
        return stderr.strip()

    return "Packet capture failed."


def _match_text(match: re.Match[str] | None) -> str:
    if not match:
        return ""

    return match.group(1).strip()


def _stop_process(process: Any) -> None:
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
    except AttributeError:
        return


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
