from __future__ import annotations

import builtins
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from pyscout import __main__
from pyscout.gui.app import launch_gui
from pyscout.storage.sqlite_store import DEFAULT_DATABASE_ENV

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None  # type: ignore[assignment]


class GuiFoundationTests(unittest.TestCase):
    def test_no_args_dispatches_to_gui(self) -> None:
        with patch("pyscout.gui.app.launch_gui", return_value=0) as launch:
            exit_code = __main__.main([])

        self.assertEqual(exit_code, 0)
        launch.assert_called_once_with()

    def test_help_still_uses_cli(self) -> None:
        with patch.object(sys, "stdout", new=io.StringIO()) as stdout:
            with self.assertRaises(SystemExit) as exit_context:
                __main__.main(["--help"])

        self.assertEqual(exit_context.exception.code, 0)
        self.assertIn("usage: pyscout", stdout.getvalue())

    def test_frozen_app_dispatches_to_gui_even_with_args(self) -> None:
        with patch.object(sys, "frozen", True, create=True):
            with patch("pyscout.gui.app.launch_gui", return_value=0) as launch:
                exit_code = __main__.main(["--help"])

        self.assertEqual(exit_code, 0)
        launch.assert_called_once_with()

    def test_pyside_import_failure_returns_clean_error(self) -> None:
        original_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "PySide6" or name.startswith("PySide6."):
                raise ModuleNotFoundError(
                    "No module named 'PySide6'",
                    name="PySide6",
                )
            return original_import(name, *args, **kwargs)

        stderr = io.StringIO()
        with patch("builtins.__import__", side_effect=fake_import):
            with redirect_stderr(stderr):
                exit_code = launch_gui([])

        error = stderr.getvalue()
        self.assertEqual(exit_code, 2)
        self.assertIn("Error: PySide6 is required", error)
        self.assertNotIn("Traceback", error)

    @unittest.skipIf(QApplication is None, "PySide6 is not installed")
    def test_main_window_only_exposes_discovery_and_mapper_tabs(self) -> None:
        from pyscout.gui.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = str(Path(tmpdir) / "pyscout.db")
            with patch.dict("os.environ", {DEFAULT_DATABASE_ENV: database_path}):
                with patch(
                    "pyscout.gui.tabs.discovery_tab.list_capture_adapters",
                    return_value=[],
                ):
                    window = MainWindow()

                    try:
                        tab_names = [
                            window.tabs.tabText(index)
                            for index in range(window.tabs.count())
                        ]
                    finally:
                        window.close()

        self.assertEqual(tab_names, ["Discovery", "Mapper"])
        self.assertNotIn("Scanner", tab_names)
        self.assertNotIn("Subnet", tab_names)
        self.assertNotIn("Tools", tab_names)

    @unittest.skipIf(QApplication is None, "PySide6 is not installed")
    def test_manual_save_record_refreshes_mapper_without_switching_tabs(self) -> None:
        from pyscout.gui.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = str(Path(tmpdir) / "pyscout.db")
            with patch.dict("os.environ", {DEFAULT_DATABASE_ENV: database_path}):
                with patch(
                    "pyscout.gui.tabs.discovery_tab.list_capture_adapters",
                    return_value=[],
                ):
                    window = MainWindow()

                    try:
                        window.tabs.setCurrentWidget(window.discovery_tab)
                        window.discovery_tab.show_result(
                            {
                                "status": "success",
                                "switch_name": "sw-1",
                                "switch_port": "Gi1/0/24",
                                "neighbor_ip": "10.0.0.1",
                                "protocol": "LLDP",
                                "backend": "scapy",
                            }
                        )
                        window.discovery_tab.save_to_mapper()
                        app.processEvents()

                        self.assertIs(window.tabs.currentWidget(), window.discovery_tab)
                        self.assertEqual(window.mapper_tab.records_table.rowCount(), 1)
                        self.assertEqual(
                            window.statusBar().currentMessage(),
                            "Record saved.",
                        )
                    finally:
                        window.close()

    @unittest.skipIf(QApplication is None, "PySide6 is not installed")
    def test_auto_save_refreshes_mapper_without_switching_tabs(self) -> None:
        from pyscout.gui.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = str(Path(tmpdir) / "pyscout.db")
            with patch.dict("os.environ", {DEFAULT_DATABASE_ENV: database_path}):
                with patch(
                    "pyscout.gui.tabs.discovery_tab.list_capture_adapters",
                    return_value=[],
                ):
                    window = MainWindow()

                    try:
                        window.tabs.setCurrentWidget(window.discovery_tab)
                        window.discovery_tab.auto_save_checkbox.setChecked(True)
                        window.discovery_tab.show_result(
                            {
                                "status": "success",
                                "switch_name": "sw-1",
                                "switch_port": "Gi1/0/24",
                                "neighbor_ip": "10.0.0.1",
                                "protocol": "CDP",
                                "backend": "scapy",
                            }
                        )
                        app.processEvents()

                        self.assertIs(window.tabs.currentWidget(), window.discovery_tab)
                        self.assertEqual(window.mapper_tab.records_table.rowCount(), 1)
                        self.assertEqual(
                            window.statusBar().currentMessage(),
                            "Completed (Scapy) — record auto-saved.",
                        )
                    finally:
                        window.close()


if __name__ == "__main__":
    unittest.main()
