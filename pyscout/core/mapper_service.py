from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pyscout.core.models import MAPPER_FIELDS, MapperRecord
from pyscout.storage.sqlite_store import SQLiteStore, open_default_store


FORM_FIELD_NAMES = tuple(field_name for field_name in MAPPER_FIELDS if field_name != "timestamp")


class MapperService:
    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or open_default_store()

    def save_record(self, values: Mapping[str, str]) -> int:
        return self.store.save_mapper_record(mapper_record_from_values(values))

    def save_discovery_result(self, result: Mapping[str, str]) -> int:
        return self.save_record(mapper_values_from_discovery(result))

    def update_record(
        self,
        record_id: int,
        values: Mapping[str, str],
        *,
        timestamp: str = "",
    ) -> bool:
        record = mapper_record_from_values(values, timestamp=timestamp)
        return self.store.update_mapper_record(record_id, record)

    def delete_record(self, record_id: int) -> bool:
        return self.store.delete_mapper_record(record_id)

    def read_rows(self) -> list[dict[str, Any]]:
        return self.store.read_mapper_record_rows()


def mapper_record_from_values(
    values: Mapping[str, str],
    *,
    timestamp: str = "",
) -> MapperRecord:
    record_values = {
        field_name: values.get(field_name, "") for field_name in FORM_FIELD_NAMES
    }
    record_values["timestamp"] = timestamp or values.get("timestamp", "")
    return MapperRecord(**record_values)


def mapper_values_from_discovery(result: Mapping[str, str]) -> dict[str, str]:
    protocol = result.get("protocol", "").strip()
    adapter = result.get("local_adapter", "").strip()
    timestamp = result.get("timestamp", "").strip()
    note_parts = [
        part
        for part in (
            f"{protocol} discovery" if protocol else "",
            f"adapter: {adapter}" if adapter else "",
            f"captured: {timestamp}" if timestamp else "",
        )
        if part
    ]

    return {
        "switch": result.get("switch_name", ""),
        "switch_port": result.get("switch_port", ""),
        "neighbor_ip": result.get("neighbor_ip", ""),
        "note": "; ".join(note_parts),
    }


__all__ = [
    "FORM_FIELD_NAMES",
    "MapperService",
    "mapper_record_from_values",
    "mapper_values_from_discovery",
]
