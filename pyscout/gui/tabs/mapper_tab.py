from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pyscout.core.mapper_service import MapperService
from pyscout.core.models import MAPPER_FIELDS
from pyscout.storage.sqlite_store import SQLiteStore


FORM_FIELDS = (
    ("site", "Site"),
    ("building", "Building"),
    ("floor", "Floor"),
    ("room", "Room"),
    ("wall_jack", "Wall Jack"),
    ("patch_panel", "Patch Panel"),
    ("switch", "Switch"),
    ("switch_port", "Port"),
    ("mac", "MAC"),
    ("vendor", "Vendor"),
    ("hostname", "Hostname"),
    ("neighbor_ip", "Neighbor IP"),
    ("note", "Note"),
)
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


try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QGridLayout,
        QGroupBox,
        QHeaderView,
        QLabel,
        QLineEdit,
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
            self.inputs: dict[str, QLineEdit] = {}
            self._rows: list[dict[str, Any]] = []
            self.selected_record_id: int | None = None
            self._selected_timestamp = ""

            self.save_button = QPushButton("Save New")
            self.update_button = QPushButton("Update Selected")
            self.delete_button = QPushButton("Delete Selected")
            self.clear_button = QPushButton("Clear Form")
            for button in (
                self.save_button,
                self.update_button,
                self.delete_button,
                self.clear_button,
            ):
                button.setFixedSize(132, 34)

            self.status_label = QLabel("Ready")
            self.status_label.setWordWrap(True)

            self.records_table = QTableWidget(0, len(TABLE_FIELDS))
            self.records_table.setHorizontalHeaderLabels(list(TABLE_HEADERS))
            self.records_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.records_table.setSelectionBehavior(
                QAbstractItemView.SelectionBehavior.SelectRows
            )
            self.records_table.setSelectionMode(
                QAbstractItemView.SelectionMode.SingleSelection
            )
            self.records_table.setAlternatingRowColors(True)
            self.records_table.verticalHeader().setVisible(False)
            self.records_table.verticalHeader().setDefaultSectionSize(30)
            self.records_table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.ResizeToContents
            )
            self.records_table.horizontalHeader().setStretchLastSection(True)
            self.records_table.setMinimumHeight(300)

            self._build_layout()
            self._connect_signals()
            self._set_selection_actions_enabled(False)
            self.refresh_records()

        def _build_layout(self) -> None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(14)

            form_group = QGroupBox("Mapper Details")
            form_layout = QGridLayout(form_group)
            form_layout.setContentsMargins(14, 16, 14, 14)
            form_layout.setHorizontalSpacing(14)
            form_layout.setVerticalSpacing(10)
            form_layout.setColumnMinimumWidth(0, 96)
            form_layout.setColumnMinimumWidth(2, 96)
            form_layout.setColumnStretch(0, 0)
            form_layout.setColumnStretch(1, 1)
            form_layout.setColumnStretch(2, 0)
            form_layout.setColumnStretch(3, 1)

            left_fields = FORM_FIELDS[:7]
            right_fields = FORM_FIELDS[7:]

            for row_index, (field_name, label_text) in enumerate(left_fields):
                self._add_form_row(form_layout, row_index, 0, field_name, label_text)

            for row_index, (field_name, label_text) in enumerate(right_fields):
                self._add_form_row(form_layout, row_index, 2, field_name, label_text)

            action_row = max(len(left_fields), len(right_fields)) + 1
            form_layout.setRowMinimumHeight(action_row - 1, 6)
            buttons = (
                self.save_button,
                self.update_button,
                self.delete_button,
                self.clear_button,
            )
            for column_index, button in enumerate(buttons):
                form_layout.addWidget(
                    button,
                    action_row,
                    column_index,
                    Qt.AlignmentFlag.AlignLeft,
                )

            records_group = QGroupBox("Saved Records")
            records_layout = QVBoxLayout(records_group)
            records_layout.setContentsMargins(16, 18, 16, 16)
            records_layout.setSpacing(10)
            records_layout.addWidget(self.records_table, stretch=1)

            layout.addWidget(form_group)
            layout.addWidget(self.status_label)
            layout.addWidget(records_group, stretch=1)

        def _add_form_row(
            self,
            layout: QGridLayout,
            row: int,
            label_column: int,
            field_name: str,
            label_text: str,
        ) -> None:
            label = QLabel(label_text)
            label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            label.setFixedWidth(96)
            field = QLineEdit()
            field.setMinimumHeight(30)
            field.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self.inputs[field_name] = field
            layout.addWidget(label, row, label_column)
            layout.addWidget(field, row, label_column + 1)

        def _connect_signals(self) -> None:
            self.save_button.clicked.connect(self.save_record)
            self.update_button.clicked.connect(self.update_record)
            self.delete_button.clicked.connect(self.delete_record)
            self.clear_button.clicked.connect(self.clear_form)
            self.records_table.itemSelectionChanged.connect(self.populate_selected_record)

        def save_record(self) -> None:
            try:
                record_id = self.service.save_record(self._form_values())
            except ValueError as exc:
                self._set_status(f"Error: {exc}")
                return

            self._clear_form()
            self.refresh_records(select_record_id=record_id)
            self._set_status("Record saved")

        def update_record(self) -> None:
            if self.selected_record_id is None:
                self._set_status("Error: select a record before updating.")
                return

            record_id = self.selected_record_id
            try:
                updated = self.service.update_record(
                    record_id,
                    self._form_values(),
                    timestamp=self._selected_timestamp,
                )
            except ValueError as exc:
                self._set_status(f"Error: {exc}")
                return

            if not updated:
                self._clear_form()
                self.refresh_records()
                self._set_status("Error: selected record no longer exists.")
                return

            self.refresh_records(select_record_id=record_id)
            self._set_status("Record updated")

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

            self._clear_form()
            self.refresh_records()

        def clear_form(self) -> None:
            self._clear_form()
            self._set_status("Ready")

        def populate_selected_record(self) -> None:
            selected_rows = self.records_table.selectionModel().selectedRows()
            if not selected_rows:
                self.selected_record_id = None
                self._selected_timestamp = ""
                self._set_selection_actions_enabled(False)
                return

            row_index = selected_rows[0].row()
            if row_index < 0 or row_index >= len(self._rows):
                self.selected_record_id = None
                self._selected_timestamp = ""
                self._set_selection_actions_enabled(False)
                return

            row = self._rows[row_index]
            self.selected_record_id = int(row["id"])
            self._selected_timestamp = str(row.get("timestamp", ""))
            for field_name, field in self.inputs.items():
                field.setText(str(row.get(field_name, "")))

            self._set_selection_actions_enabled(True)

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
                    self.records_table.setItem(row_index, column_index, item)
            self.records_table.blockSignals(False)
            self.records_table.resizeColumnsToContents()
            self.records_table.horizontalHeader().setStretchLastSection(True)

            if select_record_id is None:
                self.selected_record_id = None
                self._selected_timestamp = ""
                self._set_selection_actions_enabled(False)
                return

            self._select_record(select_record_id)

        def _clear_form(self) -> None:
            self.records_table.clearSelection()
            for field in self.inputs.values():
                field.clear()
            self.selected_record_id = None
            self._selected_timestamp = ""
            self._set_selection_actions_enabled(False)

        def _form_values(self) -> dict[str, str]:
            return {
                field_name: field.text()
                for field_name, field in self.inputs.items()
            }

        def _select_record(self, record_id: int) -> None:
            for row_index, row in enumerate(self._rows):
                if int(row["id"]) == record_id:
                    self.records_table.selectRow(row_index)
                    return

            self.selected_record_id = None
            self._selected_timestamp = ""
            self._set_selection_actions_enabled(False)

        def _set_selection_actions_enabled(self, enabled: bool) -> None:
            self.update_button.setEnabled(enabled)
            self.delete_button.setEnabled(enabled)

        def _set_status(self, message: str) -> None:
            self.status_label.setText(message)
            if self.status_callback is not None:
                self.status_callback(message)


__all__ = [
    "FORM_FIELDS",
    "MapperTab",
    "TABLE_FIELDS",
    "TABLE_HEADERS",
]
