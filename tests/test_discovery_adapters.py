from __future__ import annotations

import unittest

from pyscout.discovery.adapters import CaptureAdapter
from pyscout.discovery.adapters import auto_select_adapter, build_capture_adapter


class DiscoveryAdapterTests(unittest.TestCase):
    def test_adapter_model_maps_friendly_name_to_capture_name(self) -> None:
        adapter = build_capture_adapter(
            index=1,
            capture_name=r"\Device\NPF_{ABC}",
            name="Ethernet",
            description="Intel Ethernet Connection",
            guid="{ABC}",
            raw="<NetworkInterface_Win Intel Ethernet Connection [UP+RUNNING+OK]>",
            windows_adapters={
                "ethernet": {
                    "Status": "Up",
                    "InterfaceDescription": "Intel Ethernet Connection",
                },
            },
        )

        self.assertIsNotNone(adapter)
        assert adapter is not None
        self.assertEqual(adapter.display_name, "Ethernet - Intel Ethernet Connection (up)")
        self.assertEqual(adapter.scapy_name, r"\Device\NPF_{ABC}")
        self.assertEqual(adapter.capture_name, r"\Device\NPF_{ABC}")
        self.assertTrue(adapter.is_up)

    def test_loopback_adapter_is_filtered(self) -> None:
        adapter = build_capture_adapter(
            index=1,
            capture_name=r"\Device\NPF_Loopback",
            name="Loopback Pseudo-Interface 1",
            description="Software Loopback Interface 1",
            raw="<NetworkInterface_Win Software Loopback Interface 1 [LOOPBACK]>",
            interface_type=24,
        )

        self.assertIsNone(adapter)

    def test_auto_detect_prefers_up_ethernet_over_wifi(self) -> None:
        ethernet = CaptureAdapter(
            "1",
            r"\Device\NPF_{ETH}",
            "Ethernet",
            "raw",
            capture_name=r"\Device\NPF_{ETH}",
            description="Realtek USB GbE Family Controller",
            is_up=True,
            status_text="up",
            confidence=100,
            reason="Ethernet adapter is up",
        )
        wifi = CaptureAdapter(
            "2",
            r"\Device\NPF_{WIFI}",
            "Wi-Fi",
            "raw",
            capture_name=r"\Device\NPF_{WIFI}",
            description="Intel Wi-Fi",
            is_up=True,
            status_text="up",
            confidence=40,
            reason="Wi-Fi adapter is up",
        )

        self.assertEqual(auto_select_adapter([wifi, ethernet]), ethernet)


if __name__ == "__main__":
    unittest.main()
