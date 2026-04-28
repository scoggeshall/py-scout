from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pyscout.core.mapper_service import MapperService
from pyscout.core.models import MAPPER_FIELDS
from pyscout.storage.sqlite_store import SQLiteStore


TABLE_FIELDS = ("id", *MAPPER_FIELDS)
TABLE_HEADERS = (
    "ID",
    "Site",
    "Building",
    "Floor",
    "Room",
    "Wall Jack",
    "Patch Panel",
    "Switch",
    "Port",
    "MAC",
    "Vendor",
    "Hostname",
    "Neighbor IP",
    "Note",
    "Timestamp",
)
EDITABLE_TABLE_FIELDS = (
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
)
HIDDEN_TABLE_FIELDS = ("mac", "vendor", "hostname")


try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QMessageBox,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except ImportError:

    class MapperTab:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("PySide6 is required to use MapperTab.")

else:

    class MapperTab(QWidget):
        def __init__(
            self,
            store: SQLiteStore | None = None,
            *,
            status_callback: Callable[[str], None] | None = None,
        ) -> None:
            super().__init__()
            self.service = MapperService(store)
            self.status_callback = status_callback
            self._rows: list[dict[str, Any]] = []
            self.selected_record_id: int | None = None

            self.delete_button = QPushButton("Delete Selected")
            self.refresh_button = QPushButton("Refresh")
            for button in (self.delete_button, self.refresh_button):
                button.setMinimumSize(128, 34)

            self.help_label = QLabel("Double-click a cell to edit.")
            self.help_label.setObjectName("MapperHelpText")

            self.status_label = QLabel("Ready")
            self.status_label.setWordWrap(True)

            self.records_table = QTableWidget(0, len(TABLE_FIELDS))
            self.records_table.setHorizontalHeaderLabels(list(TABLE_HEADERS))
            self.records_table.setEditTriggers(
                QAbstractItemView.EditTrigger.DoubleClicked
                | QAbstractItemView.EditTrigger.EditKeyPressed
            )
            self.records_table.setSelectionBehavior(
                QAbstractItemView.SelectionBehavior.SelectRows
            )
            self.records_table.setSelectionMode(
                QAbstractItemView.SelectionMode.SingleSelection
            )
            self.records_table.setAlternatingRowColors(True)
            self.records_table.verticalHeader().setVisible(False)
            self.records_table.verticalHeader().setDefaultSectionSize(30)
            self.records_table.horizontalHeader().setStretchLastSection(False)
            self.records_table.setMinimumHeight(360)
            self.records_table.viewport().installEventFilter(self)

            self._build_layout()
            self._connect_signals()
            self._set_selection_actions_enabled(False)
            self.refresh_records()

        def _build_layout(self) -> None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(10)

            action_row = QWidget()
            action_layout = QHBoxLayout(action_row)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(8)
            action_layout.addWidget(self.delete_button)
            action_layout.addWidget(self.refresh_button)
            action_layout.addSpacing(8)
            action_layout.addWidget(self.help_label)
            action_layout.addStretch(1)

            records_group = QGroupBox("Saved Records")
            records_layout = QVBoxLayout(records_group)
            records_layout.setContentsMargins(16, 18, 16, 16)
            records_layout.setSpacing(10)
            records_layout.addWidget(self.records_table, stretch=1)

            layout.addWidget(action_row, stretch=0)
            layout.addWidget(self.status_label, stretch=0)
            layout.addWidget(records_group, stretch=1)

        def _connect_signals(self) -> None:
            self.delete_button.clicked.connect(self.delete_record)
            self.refresh_button.clicked.connect(lambda: self.refresh_records())
            self.records_table.itemSelectionChanged.connect(self._selection_changed)
            self.records_table.itemChanged.connect(self._persist_table_edit)

        def refresh_records(self, select_record_id: int | None = None) -> None:
            self._rows = self.service.read_rows()
            self.records_table.blockSignals(True)
            self.records_table.clearSelection()
            self.records_table.clearContents()
            self.records_table.setRowCount(len(self._rows))

            for row_index, row in enumerate(self._rows):
                for column_index, field_name in enumerate(TABLE_FIELDS):
                    item = QTableWidgetItem(str(row.get(field_name, "")))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
                    item.setFlags(self._item_flags(field_name))
                    self.records_table.setItem(row_index, column_index, item)

            self.records_table.blockSignals(False)
            self._configure_records_table()

            if select_record_id is None:
                self.selected_record_id = None
                self._set_selection_actions_enabled(False)
                return

            self._select_record(select_record_id)

        def delete_record(self) -> None:
            if self.selected_record_id is None:
                self._set_status("Error: select a record before deleting.")
                return

            record_id = self.selected_record_id
            answer = QMessageBox.question(
                self,
                "Delete Mapper Record",
                f"Delete mapper record {record_id}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

            if self.service.delete_record(record_id):
                self._set_status("Record deleted")
            else:
                self._set_status("Error: selected record no longer exists.")

            self.refresh_records()

        def _persist_table_edit(self, item: QTableWidgetItem) -> None:
            row_index = item.row()
            column_index = item.column()
            if row_index < 0 or row_index >= len(self._rows):
                return

            field_name = TABLE_FIELDS[column_index]
            if field_name not in EDITABLE_TABLE_FIELDS:
                return

            row = self._rows[row_index]
            old_value = str(row.get(field_name, ""))
            new_value = item.text()
            values = {
                name: str(row.get(name, ""))
                for name in MAPPER_FIELDS
                if name != "timestamp"
            }
            values[field_name] = new_value

            try:
                updated = self.service.update_record(
                    int(row["id"]),
                    values,
                    timestamp=str(row.get("timestamp", "")),
                )
            except ValueError as exc:
                self._set_item_text(item, old_value)
                self._set_status(f"Error: {exc}")
                return

            if not updated:
                self.refresh_records()
                self._set_status("Error: selected record no longer exists.")
                return

            row[field_name] = new_value.strip()
            self._set_status("Record updated")

        def _selection_changed(self) -> None:
            selected_rows = self.records_table.selectionModel().selectedRows()
            if not selected_rows:
                self.selected_record_id = None
                self._set_selection_actions_enabled(False)
                return

            row_index = selected_rows[0].row()
            if row_index < 0 or row_index >= len(self._rows):
                self.selected_record_id = None
                self._set_selection_actions_enabled(False)
                return

            self.selected_record_id = int(self._rows[row_index]["id"])
            self._set_selection_actions_enabled(True)

        def _select_record(self, record_id: int) -> None:
            for row_index, row in enumerate(self._rows):
                if int(row["id"]) == record_id:
                    self.records_table.selectRow(row_index)
                    return

            self.selected_record_id = None
            self._set_selection_actions_enabled(False)

        def _set_selection_actions_enabled(self, enabled: bool) -> None:
            self.delete_button.setEnabled(enabled)

        def _configure_records_table(self) -> None:
            header = self.records_table.horizontalHeader()
            header.setStretchLastSection(False)
            note_index = TABLE_FIELDS.index("note")
            for column_index, field_name in enumerate(TABLE_FIELDS):
                self.records_table.setColumnHidden(
                    column_index,
                    field_name in HIDDEN_TABLE_FIELDS,
                )
                if field_name == "note":
                    header.setSectionResizeMode(column_index, QHeaderView.ResizeMode.Stretch)
                else:
                    header.setSectionResizeMode(
                        column_index,
                        QHeaderView.ResizeMode.ResizeToContents,
                    )
            self.records_table.setColumnWidth(note_index, 260)

        def _item_flags(self, field_name: str) -> Qt.ItemFlag:
            flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            if field_name in EDITABLE_TABLE_FIELDS:
                flags |= Qt.ItemFlag.ItemIsEditable
            return flags

        def _set_item_text(self, item: QTableWidgetItem, value: str) -> None:
            self.records_table.blockSignals(True)
            item.setText(value)
            self.records_table.blockSignals(False)

        def _set_status(self, message: str) -> None:
            self.status_label.setText(message)
            if self.status_callback is not None:
                self.status_callback(message)

        def eventFilter(self, source: object, event: QEvent) -> bool:
            if (
                source is self.records_table.viewport()
                and event.type() == QEvent.Type.MouseButtonPress
            ):
                position_getter = getattr(event, "position", None)
                if callable(position_getter):
                    position = position_getter().toPoint()
                else:
                    position = event.pos()
                if self.records_table.itemAt(position) is None:
                    self.records_table.clearSelection()
            return super().eventFilter(source, event)


__all__ = [
    "EDITABLE_TABLE_FIELDS",
    "HIDDEN_TABLE_FIELDS",
    "MapperTab",
    "TABLE_FIELDS",
    "TABLE_HEADERS",
]
