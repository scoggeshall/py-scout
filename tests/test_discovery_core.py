from __future__ import annotations

import io
import unittest

from pyscout.discovery.adapters import CaptureAdapter
from pyscout.discovery.lldp_cdp import discover_from_lines, discover_lldp_cdp
from pyscout.discovery.lldp_cdp import parse_lldp_cdp_packet


class FakeProcess:
    def __init__(
        self,
        stdout_lines: list[str] | None = None,
        stderr_text: str = "",
        return_code: int = 0,
    ) -> None:
        self.stdout = iter(stdout_lines or [])
        self.stderr = io.StringIO(stderr_text)
        self.return_code = return_code

    def wait(self, timeout: int | None = None) -> int:
        return self.return_code

    def poll(self) -> int:
        return self.return_code

    def terminate(self) -> None:
        return

    def kill(self) -> None:
        return


class DiscoveryCoreTests(unittest.TestCase):
    def test_lldp_parser_with_sample_data(self) -> None:
        packet = (
            "LLDP SysN=switch-a IN/Gi1/0/12 "
            "Management Address = IPv4 10.0.0.1"
        )

        result = parse_lldp_cdp_packet(packet)

        self.assertEqual(result["protocol"], "LLDP")
        self.assertEqual(result["switch_name"], "switch-a")
        self.assertEqual(result["switch_port"], "Gi1/0/12")
        self.assertEqual(result["neighbor_ip"], "10.0.0.1")

    def test_cdp_parser_with_sample_data(self) -> None:
        packet = (
            "CDP Device ID: switch-b Port ID: Gi1/0/24 "
            "IP address: 10.0.0.2"
        )

        result = parse_lldp_cdp_packet(packet)

        self.assertEqual(result["protocol"], "CDP")
        self.assertEqual(result["switch_name"], "switch-b")
        self.assertEqual(result["switch_port"], "Gi1/0/24")
        self.assertEqual(result["neighbor_ip"], "10.0.0.2")

    def test_no_packet_found_returns_clean_timeout_result(self) -> None:
        adapter = CaptureAdapter("1", "dev", "Ethernet", "raw")

        result = discover_from_lines(adapter, [], timeout_seconds=1)

        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["local_adapter"], "Ethernet")
        self.assertIn("No LLDP/CDP packet found", result["error"])

    def test_missing_permissions_returns_clean_error(self) -> None:
        adapter = CaptureAdapter("1", "dev", "Ethernet", "raw")

        def fake_popen(*args: object, **kwargs: object) -> FakeProcess:
            return FakeProcess(
                stderr_text="You do not have permission to capture on that device.",
                return_code=1,
            )

        result = discover_lldp_cdp(adapter, timeout_seconds=1, popen_factory=fake_popen)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "Missing permission to capture packets.")


if __name__ == "__main__":
    unittest.main()
