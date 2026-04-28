from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch

from pyscout.discovery.adapters import CaptureAdapter
import pyscout.discovery.backends as discovery_backends
from pyscout.discovery.backends.scapy_backend import NPCAP_REQUIRED_MESSAGE
from pyscout.discovery.backends.scapy_backend import ScapyDiscoveryBackend
from pyscout.discovery.backends.scapy_backend import is_cdp_frame
from pyscout.discovery.backends.scapy_backend import parse_cdp_frame
from pyscout.discovery.backends.scapy_backend import parse_discovery_frame
from pyscout.discovery.backends.scapy_backend import parse_lldp_frame
from pyscout.discovery.backends.scapy_backend import parse_lldp_tlvs
from pyscout.discovery.backends.scapy_backend import parse_cdp_tlvs


def _tlv(tlv_type: int, value: bytes) -> bytes:
    return ((tlv_type << 9) | len(value)).to_bytes(2, "big") + value


def _sample_lldp_frame() -> bytes:
    destination = bytes.fromhex("0180c200000e")
    source = bytes.fromhex("001122334455")
    ethertype = bytes.fromhex("88cc")
    payload = b"".join(
        [
            _tlv(1, b"\x04" + b"chassis-a"),
            _tlv(2, b"\x05" + b"Gi1/0/12"),
            _tlv(4, b"GigabitEthernet1/0/12"),
            _tlv(5, b"switch-a"),
            _tlv(8, b"\x05\x01\x0a\x00\x00\x01\x02\x00\x00\x00\x01\x00"),
            b"\x00\x00",
        ]
    )
    return destination + source + ethertype + payload


def _lldp_frame_with_port_id(port_id_value: bytes) -> bytes:
    destination = bytes.fromhex("0180c200000e")
    source = bytes.fromhex("001122334455")
    ethertype = bytes.fromhex("88cc")
    payload = b"".join(
        [
            _tlv(2, port_id_value),
            _tlv(5, b"switch-a"),
            b"\x00\x00",
        ]
    )
    return destination + source + ethertype + payload


def _cdp_tlv(tlv_type: int, value: bytes) -> bytes:
    return tlv_type.to_bytes(2, "big") + (len(value) + 4).to_bytes(2, "big") + value


def _cdp_address(ip_address: bytes) -> bytes:
    return (
        (1).to_bytes(4, "big")
        + b"\x01\x01\xcc"
        + len(ip_address).to_bytes(2, "big")
        + ip_address
    )


def _sample_cdp_frame() -> bytes:
    destination = bytes.fromhex("01000ccccccc")
    source = bytes.fromhex("001122334455")
    cdp_payload = b"".join(
        [
            b"\x02\xb4\x00\x00",
            _cdp_tlv(0x0001, b"switch-c"),
            _cdp_tlv(0x0002, _cdp_address(b"\x0a\x00\x00\x03")),
            _cdp_tlv(0x0003, b"GigabitEthernet1/0/3"),
            _cdp_tlv(0x0004, b"\x00\x00\x00\x29"),
            _cdp_tlv(0x0005, b"Cisco IOS Software\nSecond line ignored"),
            _cdp_tlv(0x0006, b"cisco WS-C2960X"),
        ]
    )
    snap_header = bytes.fromhex("aaaa0300000c2000")
    frame_length = len(snap_header) + len(cdp_payload)
    return destination + source + frame_length.to_bytes(2, "big") + snap_header + cdp_payload


class DiscoveryBackendTests(unittest.TestCase):
    def test_scapy_backend_module_imports_cleanly(self) -> None:
        module = importlib.import_module("pyscout.discovery.backends.scapy_backend")

        self.assertTrue(hasattr(module, "ScapyDiscoveryBackend"))
        self.assertFalse(hasattr(discovery_backends, "TsharkDiscoveryBackend"))

    def test_scapy_lldp_parser_reads_standard_tlvs(self) -> None:
        parsed = parse_lldp_frame(_sample_lldp_frame())

        self.assertEqual(parsed["protocol"], "LLDP")
        self.assertEqual(parsed["switch_name"], "switch-a")
        self.assertEqual(parsed["switch_port"], "GigabitEthernet1/0/12")
        self.assertEqual(parsed["neighbor_ip"], "10.0.0.1")
        self.assertEqual(parsed["system_name"], "switch-a")
        self.assertEqual(parsed["management_ip"], "10.0.0.1")

    def test_lldp_port_id_subtype_interface_name_parses_as_text(self) -> None:
        parsed = parse_lldp_frame(_lldp_frame_with_port_id(b"\x05Gi1/0/24"))

        self.assertEqual(parsed["switch_port"], "Gi1/0/24")

    def test_lldp_port_id_subtype_mac_address_formats_mac(self) -> None:
        parsed = parse_lldp_frame(
            _lldp_frame_with_port_id(b"\x03\xaa\xbb\xcc\xdd\xee\xff")
        )

        self.assertEqual(parsed["switch_port"], "aa:bb:cc:dd:ee:ff")

    def test_lldp_port_id_empty_or_malformed_does_not_crash(self) -> None:
        parsed = parse_lldp_tlvs(
            b"".join(
                [
                    _tlv(2, b""),
                    _tlv(5, b"switch-a"),
                    b"\x00\x00",
                ]
            )
        )

        self.assertEqual(parsed["switch_name"], "switch-a")
        self.assertEqual(parsed["switch_port"], "")

    def test_lldp_port_id_unknown_subtype_falls_back_safely(self) -> None:
        parsed = parse_lldp_frame(_lldp_frame_with_port_id(b"\x09\xde\xad\xbe\xef"))

        self.assertEqual(parsed["switch_port"], "de:ad:be:ef")

    def test_lldp_parser_ignores_invalid_management_address(self) -> None:
        payload = b"".join(
            [
                _tlv(2, b"\x05" + b"Gi1/0/12"),
                _tlv(5, b"switch-a"),
                _tlv(8, b"\x05\x01\x0a\x00\x00"),
                b"\x00\x00",
            ]
        )

        parsed = parse_lldp_tlvs(payload)

        self.assertEqual(parsed["switch_name"], "switch-a")
        self.assertEqual(parsed["switch_port"], "Gi1/0/12")
        self.assertEqual(parsed["neighbor_ip"], "")

    def test_lldp_parser_ignores_unsupported_management_address_family(self) -> None:
        payload = b"".join(
            [
                _tlv(2, b"\x05" + b"Gi1/0/12"),
                _tlv(5, b"switch-a"),
                _tlv(8, b"\x05\x06\x0a\x00\x00\x01\x02\x00\x00\x00\x01\x00"),
                b"\x00\x00",
            ]
        )

        parsed = parse_lldp_tlvs(payload)

        self.assertEqual(parsed["neighbor_ip"], "")

    def test_scapy_cdp_parser_reads_standard_tlvs(self) -> None:
        parsed = parse_cdp_frame(_sample_cdp_frame())

        self.assertEqual(parsed["protocol"], "CDP")
        self.assertEqual(parsed["switch_name"], "switch-c")
        self.assertEqual(parsed["switch_port"], "GigabitEthernet1/0/3")
        self.assertEqual(parsed["neighbor_ip"], "10.0.0.3")
        self.assertEqual(parsed["device_id"], "switch-c")
        self.assertEqual(parsed["port_id"], "GigabitEthernet1/0/3")
        self.assertEqual(parsed["management_ip"], "10.0.0.3")
        self.assertEqual(parsed["capabilities"], "0x00000029")
        self.assertEqual(parsed["platform"], "cisco WS-C2960X")
        self.assertEqual(parsed["software_version"], "Cisco IOS Software")

    def test_scapy_detects_cdp_frame_by_multicast_snap_oui_and_pid(self) -> None:
        self.assertTrue(is_cdp_frame(_sample_cdp_frame()))
        self.assertFalse(is_cdp_frame(_sample_cdp_frame().replace(b"\x20\x00", b"\x20\x01", 1)))

    def test_protocol_filter_lldp_ignores_cdp(self) -> None:
        self.assertIsNone(parse_discovery_frame(_sample_cdp_frame(), protocol="lldp"))

    def test_protocol_filter_cdp_ignores_lldp(self) -> None:
        self.assertIsNone(parse_discovery_frame(_sample_lldp_frame(), protocol="cdp"))

    def test_protocol_filter_both_accepts_first_valid_protocol(self) -> None:
        adapter = CaptureAdapter("Ethernet", "Ethernet", "Ethernet", "raw")

        def fake_sniff(**kwargs: object) -> None:
            kwargs["prn"](_sample_cdp_frame())
            kwargs["prn"](_sample_lldp_frame())

        result = ScapyDiscoveryBackend(sniff_function=fake_sniff, protocol="both").discover(
            adapter,
            timeout_seconds=1,
        )

        self.assertEqual(result["protocol"], "CDP")

    def test_backend_protocol_filter_lldp_ignores_cdp_packets(self) -> None:
        adapter = CaptureAdapter("Ethernet", "Ethernet", "Ethernet", "raw")
        backend = ScapyDiscoveryBackend(
            sniff_function=lambda **kwargs: kwargs["prn"](_sample_cdp_frame()),
            protocol="lldp",
        )

        result = backend.discover(adapter, timeout_seconds=1)

        self.assertEqual(result["status"], "timeout")

    def test_backend_protocol_filter_cdp_ignores_lldp_packets(self) -> None:
        adapter = CaptureAdapter("Ethernet", "Ethernet", "Ethernet", "raw")
        backend = ScapyDiscoveryBackend(
            sniff_function=lambda **kwargs: kwargs["prn"](_sample_lldp_frame()),
            protocol="cdp",
        )

        result = backend.discover(adapter, timeout_seconds=1)

        self.assertEqual(result["status"], "timeout")

    def test_cdp_parser_ignores_short_or_malformed_tlvs(self) -> None:
        self.assertIsNone(parse_cdp_tlvs(b"\x02\xb4\x00"))
        self.assertIsNone(parse_cdp_tlvs(b"\x02\xb4\x00\x00\x00\x01\x00\x03"))

    def test_scapy_backend_discovers_cdp_packet(self) -> None:
        adapter = CaptureAdapter("Ethernet", "Ethernet", "Ethernet", "raw")
        backend = ScapyDiscoveryBackend(
            sniff_function=lambda **kwargs: kwargs["prn"](_sample_cdp_frame())
        )

        result = backend.discover(adapter, timeout_seconds=1)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["backend"], "scapy")
        self.assertEqual(result["protocol"], "CDP")
        self.assertEqual(result["switch_name"], "switch-c")
        self.assertEqual(result["platform"], "cisco WS-C2960X")

    def test_scapy_backend_discovers_lldp_packet(self) -> None:
        adapter = CaptureAdapter("Ethernet", "Ethernet", "Ethernet", "raw")
        backend = ScapyDiscoveryBackend(
            sniff_function=lambda **kwargs: kwargs["prn"](_sample_lldp_frame())
        )

        result = backend.discover(adapter, timeout_seconds=1)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["backend"], "scapy")
        self.assertEqual(result["protocol"], "LLDP")
        self.assertEqual(result["switch_name"], "switch-a")

    def test_missing_scapy_returns_clean_unavailable_result(self) -> None:
        adapter = CaptureAdapter("Ethernet", "Ethernet", "Ethernet", "raw")
        backend = ScapyDiscoveryBackend()

        with patch("importlib.import_module", side_effect=ImportError):
            result = backend.discover(adapter, timeout_seconds=1)

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["backend"], "scapy")
        self.assertIn("Scapy is not installed", result["error"])

    def test_missing_npcap_returns_clear_capture_requirement(self) -> None:
        adapter = CaptureAdapter("Ethernet", "Ethernet", "Ethernet", "raw")

        def fake_sniff(**kwargs: object) -> None:
            raise OSError("libpcap is not available. Cannot compile filter.")

        result = ScapyDiscoveryBackend(sniff_function=fake_sniff).discover(
            adapter,
            timeout_seconds=1,
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["backend"], "scapy")
        self.assertEqual(result["error"], NPCAP_REQUIRED_MESSAGE)


if __name__ == "__main__":
    unittest.main()
