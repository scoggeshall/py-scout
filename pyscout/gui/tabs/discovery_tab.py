from __future__ import annotations

from collections.abc import Callable, Mapping
from threading import Event

from pyscout.core.mapper_service import MapperService
from pyscout.discovery.adapters import AdapterDiscoveryError, CaptureAdapter
from pyscout.discovery.adapters import auto_select_adapter, list_capture_adapters
from pyscout.discovery.backends import DiscoveryProtocol
from pyscout.discovery.lldp_cdp import discover_lldp_cdp
from pyscout.storage.sqlite_store import SQLiteStore


DEFAULT_DISCOVERY_TIMEOUT_SECONDS = 90
RESULT_FIELDS = (
    ("switch_name", "Switch Name"),
    ("switch_port", "Switch Port"),
    ("neighbor_ip", "Neighbor IP"),
    ("protocol", "Protocol"),
    ("backend", "Discovery Engine"),
    ("timestamp", "Timestamp"),
)
PROTOCOL_OPTIONS: tuple[tuple[str, DiscoveryProtocol], ...] = (
    ("Both LLDP/CDP", "both"),
    ("LLDP only", "lldp"),
    ("CDP only", "cdp"),
)
try:
    from PySide6.QtCore import QObject, Qt, QThread, Signal
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QCheckBox,
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

    class DiscoveryWorker(QObject):
        finished = Signal(dict)

        def __init__(
            self,
            adapter: CaptureAdapter,
            timeout_seconds: int,
            protocol: DiscoveryProtocol,
        ) -> None:
            super().__init__()
            self.adapter = adapter
            self.timeout_seconds = timeout_seconds
            self.protocol = protocol
            self.cancel_event = Event()

        def cancel(self) -> None:
            self.cancel_event.set()

        def run(self) -> None:
            self.finished.emit(
                discover_lldp_cdp(
                    self.adapter,
                    self.timeout_seconds,
                    protocol=self.protocol,
                    cancel_event=self.cancel_event,
                )
            )


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
            self.discovery_thread: QThread | None = None
            self.discovery_worker: DiscoveryWorker | None = None

            self.adapter_combo = QComboBox()
            self.adapter_combo.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            self.protocol_combo = QComboBox()
            for label, protocol in PROTOCOL_OPTIONS:
                self.protocol_combo.addItem(label, protocol)
            self.protocol_combo.setMinimumWidth(160)
            self.protocol_combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToContents
            )
            self.engine_value_label = QLabel("Scapy")

            self.auto_select_button = QPushButton("Auto-detect Adapter")
            self.discover_button = QPushButton("Run Discovery")
            self.cancel_button = QPushButton("Cancel Discovery")
            self.save_mapper_button = QPushButton("Save Record")
            self.auto_save_checkbox = QCheckBox("Auto Save")
            self.current_result_saved_id: int | None = None

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
            self._set_running(False)
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
            protocol_label = QLabel("Discovery Protocol")
            protocol_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            inputs_layout.addRow(protocol_label, self.protocol_combo)
            engine_label = QLabel("Discovery Engine")
            engine_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            inputs_layout.addRow(engine_label, self.engine_value_label)

            actions_group = QGroupBox("Actions")
            actions_layout = QHBoxLayout(actions_group)
            actions_layout.setContentsMargins(16, 18, 16, 16)
            actions_layout.setSpacing(8)
            actions_layout.addWidget(self.auto_select_button)
            actions_layout.addWidget(self.discover_button)
            actions_layout.addWidget(self.cancel_button)
            actions_layout.addWidget(self.save_mapper_button)
            actions_layout.addWidget(self.auto_save_checkbox)
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
            self.cancel_button.clicked.connect(self.cancel_discovery)
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
            if self.discovery_thread is not None:
                return

            adapter = self.adapter_combo.currentData()
            message = adapter_required_message(adapter)
            if message:
                self._set_status(message)
                return

            self._set_status("Running discovery...")
            self._set_running(True)
            self.discovery_thread = QThread(self)
            self.discovery_worker = DiscoveryWorker(
                adapter,
                DEFAULT_DISCOVERY_TIMEOUT_SECONDS,
                self._selected_protocol(),
            )
            self.discovery_worker.moveToThread(self.discovery_thread)
            self.discovery_thread.started.connect(self.discovery_worker.run)
            self.discovery_worker.finished.connect(self._discovery_finished)
            self.discovery_worker.finished.connect(self.discovery_thread.quit)
            self.discovery_worker.finished.connect(self.discovery_worker.deleteLater)
            self.discovery_thread.finished.connect(self._discovery_thread_finished)
            self.discovery_thread.start()

        def cancel_discovery(self) -> None:
            if self.discovery_worker is None:
                return

            self.discovery_worker.cancel()
            self.cancel_button.setEnabled(False)
            self._set_status("Discovery canceled.")

        def show_result(self, result: dict[str, str]) -> None:
            self.current_result = result
            self.current_result_saved_id = None
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
                backend = result.get("backend", "").strip()
                backend = _display_backend(backend)
                message = f"Completed ({backend})" if backend else "Completed"
                self._set_result_actions_enabled(True)
                if self.auto_save_checkbox.isChecked():
                    self._save_current_result(
                        saved_message=f"{message} — record auto-saved.",
                    )
                else:
                    self._set_status(message)
                return

            if result.get("status") == "canceled":
                self._set_result_actions_enabled(False)
                self._set_status("Discovery canceled.")
                return

            self._set_result_actions_enabled(False)
            self._set_status(f"Error: {result.get('error', 'Discovery failed.')}")

        def _discovery_finished(self, result: dict[str, str]) -> None:
            self._set_running(False)
            self.show_result(result)

        def _discovery_thread_finished(self) -> None:
            if self.discovery_thread is not None:
                self.discovery_thread.deleteLater()
            self.discovery_thread = None
            self.discovery_worker = None

        def save_to_mapper(self) -> None:
            self._save_current_result(saved_message="Record saved.")

        def _save_current_result(self, *, saved_message: str) -> bool:
            if not self.current_result:
                self._set_status("Error: run discovery before saving to Mapper.")
                return False

            if self.current_result.get("status") != "success":
                self._set_status("Error: run a successful discovery before saving.")
                return False

            if self.current_result_saved_id is not None:
                self._set_status("Record already saved for this discovery result.")
                return False

            try:
                record_id = self.service.save_discovery_result(self.current_result)
            except ValueError as exc:
                self._set_status(f"Error: {exc}")
                return False

            self.current_result_saved_id = record_id
            self.mapper_record_saved.emit(record_id)
            self._set_status(saved_message)
            self._set_result_actions_enabled(False)
            return True

        def _set_result_actions_enabled(self, enabled: bool) -> None:
            self.save_mapper_button.setEnabled(
                enabled and self.current_result_saved_id is None
            )

        def _set_running(self, running: bool) -> None:
            self.adapter_combo.setEnabled(not running)
            self.protocol_combo.setEnabled(not running)
            self.auto_select_button.setEnabled(not running)
            self.discover_button.setEnabled(not running)
            self.cancel_button.setEnabled(running)
            if running:
                self.save_mapper_button.setEnabled(False)

        def _selected_protocol(self) -> DiscoveryProtocol:
            protocol = self.protocol_combo.currentData()
            return protocol if protocol in {"both", "lldp", "cdp"} else "both"

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
        if field_name == "backend":
            value = _display_backend(value)
        if field_name == "timestamp" and not value:
            continue
        rows.append([label, value])
    return rows


def _display_backend(value: str) -> str:
    return "Scapy" if value == "scapy" else value


__all__ = [
    "DEFAULT_DISCOVERY_TIMEOUT_SECONDS",
    "DiscoveryTab",
    "PROTOCOL_OPTIONS",
    "adapter_required_message",
    "discovery_result_to_rows",
]
