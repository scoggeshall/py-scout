from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pyscout.core.models import MapperRecord
from pyscout.storage.sqlite_store import SQLiteStore

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - exercised when PySide6 is unavailable.
    QApplication = None  # type: ignore[assignment]


class MapperGuiTabTests(unittest.TestCase):
    def test_mapper_tab_imports_cleanly(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.mapper_tab")

        self.assertTrue(hasattr(module, "MapperTab"))

    def test_mapper_field_order_matches_two_column_layout(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.mapper_tab")

        self.assertEqual(
            module.FORM_FIELDS[:7],
            (
                ("site", "Site"),
                ("building", "Building"),
                ("floor", "Floor"),
                ("room", "Room"),
                ("wall_jack", "Wall Jack"),
                ("patch_panel", "Patch Panel"),
                ("switch", "Switch"),
            ),
        )
        self.assertEqual(
            module.FORM_FIELDS[7:],
            (
                ("switch_port", "Port"),
                ("mac", "MAC"),
                ("vendor", "Vendor"),
                ("hostname", "Hostname"),
                ("neighbor_ip", "Neighbor IP"),
                ("note", "Note"),
            ),
        )

    @unittest.skipIf(QApplication is None, "PySide6 is not installed")
    def test_select_edit_update_and_delete_mapper_record(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.mapper_tab")
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteStore(Path(tmpdir) / "pyscout.db")
            record_id = store.save_mapper_record(
                MapperRecord(site="Main", wall_jack="A-12", room="214")
            )
            tab = module.MapperTab(store)

            try:
                self.assertFalse(tab.update_button.isEnabled())
                self.assertFalse(tab.delete_button.isEnabled())

                tab.records_table.selectRow(0)
                app.processEvents()

                self.assertEqual(tab.selected_record_id, record_id)
                self.assertEqual(tab.inputs["room"].text(), "214")
                self.assertTrue(tab.update_button.isEnabled())
                self.assertTrue(tab.delete_button.isEnabled())

                tab.inputs["room"].setText("215")
                tab.update_record()

                rows = store.read_mapper_record_rows()
                self.assertEqual(rows[0]["id"], record_id)
                self.assertEqual(rows[0]["room"], "215")

                with patch.object(
                    module.QMessageBox,
                    "question",
                    return_value=module.QMessageBox.StandardButton.Yes,
                ):
                    tab.delete_record()

                self.assertEqual(store.read_mapper_record_rows(), [])
            finally:
                tab.close()


if __name__ == "__main__":
    unittest.main()
