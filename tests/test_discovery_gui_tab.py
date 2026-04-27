from __future__ import annotations

import importlib
import unittest


class DiscoveryGuiTabTests(unittest.TestCase):
    def test_discovery_tab_imports_cleanly(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.discovery_tab")

        self.assertTrue(hasattr(module, "DiscoveryTab"))

    def test_no_adapter_selected_shows_clean_gui_message(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.discovery_tab")

        self.assertEqual(
            module.adapter_required_message(None),
            "Error: select an adapter before starting discovery.",
        )

    def test_discovery_rows_show_core_result_fields(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.discovery_tab")

        rows = module.discovery_result_to_rows(
            {
                "switch_name": "sw-1",
                "switch_port": "Gi1/0/12",
                "neighbor_ip": "10.0.0.1",
                "protocol": "LLDP",
                "timestamp": "2026-04-27T09:00:00-04:00",
            }
        )

        self.assertEqual(
            rows,
            [
                ["Switch Name", "sw-1"],
                ["Switch Port", "Gi1/0/12"],
                ["Neighbor IP", "10.0.0.1"],
                ["Protocol", "LLDP"],
                ["Timestamp", "2026-04-27T09:00:00-04:00"],
            ],
        )


if __name__ == "__main__":
    unittest.main()
