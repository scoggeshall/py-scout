from __future__ import annotations

from collections.abc import Callable, Mapping

from pyscout.core.mapper_service import MapperService
from pyscout.discovery.adapters import AdapterDiscoveryError, CaptureAdapter
from pyscout.discovery.adapters import auto_select_adapter, list_capture_adapters
from pyscout.discovery.lldp_cdp import discover_lldp_cdp
from pyscout.storage.sqlite_store import SQLiteStore


DEFAULT_DISCOVERY_TIMEOUT_SECONDS = 90
RESULT_FIELDS = (
    ("switch_name", "Switch Name"),
    ("switch_port", "Switch Port"),
    ("neighbor_ip", "Neighbor IP"),
    ("protocol", "Protocol"),
    ("timestamp", "Timestamp"),
)


try:
    from PySide6.QtCore import QCoreApplication, Qt, Signal
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QComboBox,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QPushButton,
        QSizePolicy,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except ImportError:

    class DiscoveryTab:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("PySide6 is required to use DiscoveryTab.")

else:

    class DiscoveryTab(QWidget):
        mapper_record_saved = Signal(int)

        def __init__(
            self,
            store: SQLiteStore | None = None,
            *,
            status_callback: Callable[[str], None] | None = None,
        ) -> None:
            super().__init__()
            self.service = MapperService(store)
            self.status_callback = status_callback
            self.adapters: list[CaptureAdapter] = []
            self.current_result: dict[str, str] | None = None

            self.adapter_combo = QComboBox()
            self.adapter_combo.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )

            self.auto_select_button = QPushButton("Auto-detect Adapter")
            self.discover_button = QPushButton("Run Discovery")
            self.save_mapper_button = QPushButton("Save to Mapper")

            self.status_label = QLabel("Ready")
            self.status_label.setWordWrap(True)

            self.results_table = QTableWidget(0, 2)
            self.results_table.setHorizontalHeaderLabels(["Field", "Value"])
            self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.results_table.setSelectionBehavior(
                QAbstractItemView.SelectionBehavior.SelectRows
            )
            self.results_table.setAlternatingRowColors(True)
            self.results_table.verticalHeader().setVisible(False)
            self.results_table.verticalHeader().setDefaultSectionSize(30)
            self.results_table.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.ResizeMode.ResizeToContents
            )
            self.results_table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.ResizeMode.Stretch
            )
            self.results_table.setMinimumHeight(260)

            self._build_layout()
            self._connect_signals()
            self._set_result_actions_enabled(False)
            self._set_status("Ready")
            self.refresh_adapters()

        def _build_layout(self) -> None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(12)

            inputs_group = QGroupBox("Discovery")
            inputs_layout = QFormLayout(inputs_group)
            inputs_layout.setContentsMargins(16, 18, 16, 16)
            inputs_layout.setHorizontalSpacing(12)
            inputs_layout.setVerticalSpacing(10)
            inputs_layout.setFieldGrowthPolicy(
                QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
            )

            adapter_label = QLabel("Adapter")
            adapter_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            inputs_layout.addRow(adapter_label, self.adapter_combo)

            actions_group = QGroupBox("Actions")
            actions_layout = QHBoxLayout(actions_group)
            actions_layout.setContentsMargins(16, 18, 16, 16)
            actions_layout.setSpacing(8)
            actions_layout.addWidget(self.auto_select_button)
            actions_layout.addWidget(self.discover_button)
            actions_layout.addWidget(self.save_mapper_button)
            actions_layout.addStretch(1)

            results_group = QGroupBox("Results")
            results_layout = QVBoxLayout(results_group)
            results_layout.setContentsMargins(16, 18, 16, 16)
            results_layout.setSpacing(10)
            results_layout.addWidget(self.results_table)

            layout.addWidget(inputs_group)
            layout.addWidget(actions_group)
            layout.addWidget(self.status_label)
            layout.addWidget(results_group, stretch=1)

        def _connect_signals(self) -> None:
            self.auto_select_button.clicked.connect(self.auto_select)
            self.discover_button.clicked.connect(self.discover)
            self.save_mapper_button.clicked.connect(self.save_to_mapper)

        def refresh_adapters(self) -> None:
            self.adapter_combo.clear()
            try:
                self.adapters = list_capture_adapters()
            except AdapterDiscoveryError as exc:
                self.adapters = []
                self.adapter_combo.addItem("No adapters available", None)
                self._set_status(f"Error: {exc}")
                return

            self.adapter_combo.addItem("Select an adapter", None)
            for adapter in self.adapters:
                self.adapter_combo.addItem(adapter.display_name, adapter)

            if not self.adapters:
                self._set_status("Error: no capture adapters were found.")

        def auto_select(self) -> None:
            try:
                selected = auto_select_adapter(self.adapters)
            except AdapterDiscoveryError as exc:
                self._set_status(f"Error: {exc}")
                return

            for index in range(self.adapter_combo.count()):
                adapter = self.adapter_combo.itemData(index)
                if adapter == selected:
                    self.adapter_combo.setCurrentIndex(index)
                    break

            self._set_status(f"Selected {selected.name}")

        def discover(self) -> None:
            adapter = self.adapter_combo.currentData()
            message = adapter_required_message(adapter)
            if message:
                self._set_status(message)
                return

            self._set_status("Running")
            QCoreApplication.processEvents()
            result = discover_lldp_cdp(adapter, DEFAULT_DISCOVERY_TIMEOUT_SECONDS)
            self.show_result(result)

        def show_result(self, result: dict[str, str]) -> None:
            self.current_result = result
            rows = discovery_result_to_rows(result)
            self.results_table.setRowCount(len(rows))

            for row_index, row in enumerate(rows):
                for column_index, value in enumerate(row):
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
                    self.results_table.setItem(row_index, column_index, item)
            self.results_table.resizeColumnsToContents()
            self.results_table.horizontalHeader().setStretchLastSection(True)

            if result.get("status") == "success":
                self._set_status("Completed")
                self._set_result_actions_enabled(True)
                return

            self._set_result_actions_enabled(False)
            self._set_status(f"Error: {result.get('error', 'Discovery failed.')}")

        def save_to_mapper(self) -> None:
            if not self.current_result:
                self._set_status("Error: run discovery before saving to Mapper.")
                return

            try:
                record_id = self.service.save_discovery_result(self.current_result)
            except ValueError as exc:
                self._set_status(f"Error: {exc}")
                return

            self.mapper_record_saved.emit(record_id)
            self._set_status("Record saved")

        def _set_result_actions_enabled(self, enabled: bool) -> None:
            self.save_mapper_button.setEnabled(enabled)

        def _set_status(self, message: str) -> None:
            self.status_label.setText(message)
            if self.status_callback is not None:
                self.status_callback(message)


def adapter_required_message(adapter: object | None) -> str:
    if adapter is None:
        return "Error: select an adapter before starting discovery."

    return ""


def discovery_result_to_rows(result: Mapping[str, str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for field_name, label in RESULT_FIELDS:
        value = result.get(field_name, "")
        if field_name == "timestamp" and not value:
            continue
        rows.append([label, value])
    return rows


__all__ = [
    "DEFAULT_DISCOVERY_TIMEOUT_SECONDS",
    "DiscoveryTab",
    "adapter_required_message",
    "discovery_result_to_rows",
]
