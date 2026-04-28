from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pyscout.discovery.adapters import CaptureAdapter
from pyscout.storage.sqlite_store import SQLiteStore

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None  # type: ignore[assignment]


class DiscoveryGuiTabTests(unittest.TestCase):
    def test_discovery_tab_imports_cleanly(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.discovery_tab")

        self.assertTrue(hasattr(module, "DiscoveryTab"))
        self.assertFalse(hasattr(module, "DISCOVERY_ENGINES"))

    def test_protocol_dropdown_options_are_available(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.discovery_tab")

        self.assertEqual(
            module.PROTOCOL_OPTIONS,
            (
                ("Both LLDP/CDP", "both"),
                ("LLDP only", "lldp"),
                ("CDP only", "cdp"),
            ),
        )

    @unittest.skipIf(QApplication is None, "PySide6 is not installed")
    def test_protocol_dropdown_exists_in_discovery_tab(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.discovery_tab")

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteStore(Path(tmpdir) / "pyscout.db")
            with patch.object(module, "list_capture_adapters", return_value=[]):
                tab = module.DiscoveryTab(store)
                try:
                    labels = [
                        tab.protocol_combo.itemText(index)
                        for index in range(tab.protocol_combo.count())
                    ]
                    engine_text = tab.engine_value_label.text()
                    protocol_width = tab.protocol_combo.minimumWidth()
                    save_button_text = tab.save_mapper_button.text()
                    auto_save_checked = tab.auto_save_checkbox.isChecked()
                finally:
                    tab.close()

        self.assertEqual(labels, ["Both LLDP/CDP", "LLDP only", "CDP only"])
        self.assertEqual(engine_text, "Scapy")
        self.assertGreaterEqual(protocol_width, 160)
        self.assertEqual(save_button_text, "Save Record")
        self.assertFalse(auto_save_checked)

    @unittest.skipIf(QApplication is None, "PySide6 is not installed")
    def test_cancel_button_enabled_only_while_running(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.discovery_tab")

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteStore(Path(tmpdir) / "pyscout.db")
            with patch.object(module, "list_capture_adapters", return_value=[]):
                tab = module.DiscoveryTab(store)
                try:
                    self.assertFalse(tab.cancel_button.isEnabled())

                    tab._set_running(True)
                    self.assertFalse(tab.discover_button.isEnabled())
                    self.assertFalse(tab.adapter_combo.isEnabled())
                    self.assertFalse(tab.protocol_combo.isEnabled())
                    self.assertTrue(tab.cancel_button.isEnabled())

                    tab._set_running(False)
                    self.assertTrue(tab.discover_button.isEnabled())
                    self.assertTrue(tab.adapter_combo.isEnabled())
                    self.assertTrue(tab.protocol_combo.isEnabled())
                    self.assertFalse(tab.cancel_button.isEnabled())
                finally:
                    tab.close()

    @unittest.skipIf(QApplication is None, "PySide6 is not installed")
    def test_discovery_worker_cancel_sets_cancel_event(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.discovery_tab")
        adapter = CaptureAdapter("1", "dev", "Ethernet", "raw")

        worker = module.DiscoveryWorker(adapter, 1, "both")
        worker.cancel()

        self.assertTrue(worker.cancel_event.is_set())

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
                ["Discovery Engine", ""],
                ["Timestamp", "2026-04-27T09:00:00-04:00"],
            ],
        )

    def test_discovery_rows_show_backend_when_present(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.discovery_tab")

        rows = module.discovery_result_to_rows(
            {
                "switch_name": "sw-1",
                "backend": "scapy",
            }
        )

        self.assertIn(["Discovery Engine", "Scapy"], rows)

    @unittest.skipIf(QApplication is None, "PySide6 is not installed")
    def test_manual_save_record_saves_current_discovery_result_once(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.discovery_tab")

        QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteStore(Path(tmpdir) / "pyscout.db")
            with patch.object(module, "list_capture_adapters", return_value=[]):
                tab = module.DiscoveryTab(store)
                try:
                    tab.show_result(
                        {
                            "status": "success",
                            "switch_name": "sw-1",
                            "switch_port": "Gi1/0/24",
                            "neighbor_ip": "10.0.0.1",
                            "protocol": "LLDP",
                            "backend": "scapy",
                        }
                    )

                    self.assertTrue(tab.save_mapper_button.isEnabled())
                    tab.save_to_mapper()
                    self.assertEqual(tab.status_label.text(), "Record saved.")
                    tab.save_to_mapper()

                    rows = store.read_mapper_record_rows()
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]["switch"], "sw-1")
                    self.assertEqual(rows[0]["switch_port"], "Gi1/0/24")
                    self.assertFalse(tab.save_mapper_button.isEnabled())
                    self.assertEqual(
                        tab.status_label.text(),
                        "Record already saved for this discovery result.",
                    )
                finally:
                    tab.close()

    @unittest.skipIf(QApplication is None, "PySide6 is not installed")
    def test_auto_save_saves_once_per_successful_discovery_run(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.discovery_tab")

        QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteStore(Path(tmpdir) / "pyscout.db")
            with patch.object(module, "list_capture_adapters", return_value=[]):
                tab = module.DiscoveryTab(store)
                try:
                    tab.auto_save_checkbox.setChecked(True)
                    result = {
                        "status": "success",
                        "switch_name": "sw-1",
                        "switch_port": "Gi1/0/24",
                        "neighbor_ip": "10.0.0.1",
                        "protocol": "CDP",
                        "backend": "scapy",
                    }

                    tab.show_result(result)
                    tab.save_to_mapper()

                    rows = store.read_mapper_record_rows()
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]["switch"], "sw-1")
                    self.assertEqual(rows[0]["switch_port"], "Gi1/0/24")
                    self.assertFalse(tab.save_mapper_button.isEnabled())
                    self.assertEqual(
                        tab.status_label.text(),
                        "Record already saved for this discovery result.",
                    )

                    tab.show_result(result | {"switch_port": "Gi1/0/25"})

                    rows = store.read_mapper_record_rows()
                    self.assertEqual(len(rows), 2)
                    self.assertEqual(rows[1]["switch_port"], "Gi1/0/25")
                    self.assertEqual(
                        tab.status_label.text(),
                        "Completed (Scapy) — record auto-saved.",
                    )
                finally:
                    tab.close()


if __name__ == "__main__":
    unittest.main()
