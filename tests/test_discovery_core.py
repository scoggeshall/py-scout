from __future__ import annotations

from threading import Event
import unittest

from pyscout.discovery.adapters import CaptureAdapter
from pyscout.discovery.lldp_cdp import discover_lldp_cdp


class DiscoveryCoreTests(unittest.TestCase):
    def test_no_packet_found_returns_clean_timeout_result(self) -> None:
        adapter = CaptureAdapter("1", "dev", "Ethernet", "raw")

        def fake_sniff(**kwargs: object) -> None:
            return

        result = discover_lldp_cdp(
            adapter,
            timeout_seconds=1,
            sniff_function=fake_sniff,
        )

        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["local_adapter"], "Ethernet")
        self.assertEqual(result["backend"], "scapy")
        self.assertEqual(result["error"], "No LLDP/CDP packets received before timeout.")

    def test_missing_permissions_returns_clean_error(self) -> None:
        adapter = CaptureAdapter("1", "dev", "Ethernet", "raw")

        def fake_sniff(**kwargs: object) -> None:
            raise PermissionError("access denied")

        result = discover_lldp_cdp(
            adapter,
            timeout_seconds=1,
            sniff_function=fake_sniff,
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["backend"], "scapy")
        self.assertEqual(result["error"], "Missing permission to capture packets.")

    def test_cancel_event_stops_discovery_cleanly(self) -> None:
        adapter = CaptureAdapter("1", "dev", "Ethernet", "raw")
        cancel_event = Event()

        def fake_sniff(**kwargs: object) -> None:
            cancel_event.set()

        result = discover_lldp_cdp(
            adapter,
            timeout_seconds=30,
            sniff_function=fake_sniff,
            cancel_event=cancel_event,
        )

        self.assertEqual(result["status"], "canceled")
        self.assertEqual(result["error"], "Discovery canceled.")


if __name__ == "__main__":
    unittest.main()
