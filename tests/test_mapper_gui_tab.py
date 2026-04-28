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
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QHeaderView
except ImportError:  # pragma: no cover - exercised when PySide6 is unavailable.
    QApplication = None  # type: ignore[assignment]
    QHeaderView = None  # type: ignore[assignment]
    Qt = None  # type: ignore[assignment]


class MapperGuiTabTests(unittest.TestCase):
    def test_mapper_tab_imports_cleanly(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.mapper_tab")

        self.assertTrue(hasattr(module, "MapperTab"))

    def test_mapper_table_configuration_matches_table_first_workflow(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.mapper_tab")

        self.assertEqual(
            module.EDITABLE_TABLE_FIELDS,
            (
                "site",
                "building",
                "floor",
                "room",
                "wall_jack",
                "patch_panel",
                "switch",
                "switch_port",
                "neighbor_ip",
                "note",
            ),
        )
        self.assertEqual(module.HIDDEN_TABLE_FIELDS, ("mac", "vendor", "hostname"))

    @unittest.skipIf(QApplication is None, "PySide6 is not installed")
    def test_mapper_table_loads_records_and_omits_removed_form_controls(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.mapper_tab")
        QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteStore(Path(tmpdir) / "pyscout.db")
            store.save_mapper_record(MapperRecord(site="Main", switch="sw-1"))
            tab = module.MapperTab(store)

            try:
                self.assertEqual(tab.records_table.rowCount(), 1)
                self.assertEqual(
                    tab.records_table.item(0, module.TABLE_FIELDS.index("site")).text(),
                    "Main",
                )
                self.assertTrue(hasattr(tab, "delete_button"))
                self.assertTrue(hasattr(tab, "refresh_button"))
                self.assertFalse(hasattr(tab, "save_button"))
                self.assertFalse(hasattr(tab, "update_button"))
                self.assertFalse(hasattr(tab, "clear_button"))
                self.assertGreaterEqual(tab.records_table.minimumHeight(), 360)
                self.assertEqual(
                    tab.records_table.horizontalHeader().sectionResizeMode(
                        module.TABLE_FIELDS.index("note")
                    ),
                    QHeaderView.ResizeMode.Stretch,
                )
            finally:
                tab.close()

    @unittest.skipIf(QApplication is None, "PySide6 is not installed")
    def test_table_edits_persist_immediately(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.mapper_tab")
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteStore(Path(tmpdir) / "pyscout.db")
            record_id = store.save_mapper_record(
                MapperRecord(site="Main", wall_jack="A-12", room="214")
            )
            tab = module.MapperTab(store)

            try:
                room_column = module.TABLE_FIELDS.index("room")
                note_column = module.TABLE_FIELDS.index("note")

                tab.records_table.item(0, room_column).setText("215")
                tab.records_table.item(0, note_column).setText("Cable replaced.")
                app.processEvents()

                rows = store.read_mapper_record_rows()
                self.assertEqual(rows[0]["id"], record_id)
                self.assertEqual(rows[0]["room"], "215")
                self.assertEqual(rows[0]["note"], "Cable replaced.")
                self.assertEqual(tab.status_label.text(), "Record updated")
            finally:
                tab.close()

    @unittest.skipIf(QApplication is None, "PySide6 is not installed")
    def test_id_timestamp_and_hidden_fields_are_not_editable(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.mapper_tab")
        QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteStore(Path(tmpdir) / "pyscout.db")
            store.save_mapper_record(MapperRecord(site="Main", mac="aa:bb"))
            tab = module.MapperTab(store)

            try:
                for field_name in ("id", "timestamp", "mac", "vendor", "hostname"):
                    column = module.TABLE_FIELDS.index(field_name)
                    flags = tab.records_table.item(0, column).flags()
                    self.assertFalse(flags & Qt.ItemFlag.ItemIsEditable)

                for field_name in module.HIDDEN_TABLE_FIELDS:
                    self.assertTrue(
                        tab.records_table.isColumnHidden(
                            module.TABLE_FIELDS.index(field_name)
                        )
                    )
            finally:
                tab.close()

    @unittest.skipIf(QApplication is None, "PySide6 is not installed")
    def test_delete_selected_works_with_confirmation(self) -> None:
        module = importlib.import_module("pyscout.gui.tabs.mapper_tab")
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteStore(Path(tmpdir) / "pyscout.db")
            record_id = store.save_mapper_record(MapperRecord(site="Main"))
            tab = module.MapperTab(store)

            try:
                self.assertFalse(tab.delete_button.isEnabled())

                tab.records_table.selectRow(0)
                app.processEvents()

                self.assertEqual(tab.selected_record_id, record_id)
                self.assertTrue(tab.delete_button.isEnabled())

                with patch.object(
                    module.QMessageBox,
                    "question",
                    return_value=module.QMessageBox.StandardButton.Yes,
                ):
                    tab.delete_record()

                self.assertEqual(store.read_mapper_record_rows(), [])
                self.assertEqual(tab.records_table.rowCount(), 0)
                self.assertFalse(tab.delete_button.isEnabled())
            finally:
                tab.close()


if __name__ == "__main__":
    unittest.main()
