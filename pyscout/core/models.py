from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


MAPPER_FIELDS = (
    "site",
    "building",
    "floor",
    "room",
    "wall_jack",
    "patch_panel",
    "switch",
    "switch_port",
    "mac",
    "vendor",
    "hostname",
    "neighbor_ip",
    "note",
    "timestamp",
)
REQUIRED_MAPPER_FIELDS: tuple[str, ...] = ()
MAPPER_CONTENT_FIELDS = tuple(field_name for field_name in MAPPER_FIELDS if field_name != "timestamp")


class MapperValidationError(ValueError):
    """Raised when a mapper record is missing required data."""


def _current_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class MapperRecord:
    site: str = ""
    building: str = ""
    floor: str = ""
    room: str = ""
    wall_jack: str = ""
    patch_panel: str = ""
    switch: str = ""
    switch_port: str = ""
    mac: str = ""
    vendor: str = ""
    hostname: str = ""
    neighbor_ip: str = ""
    note: str = ""
    timestamp: str = field(default_factory=_current_timestamp)

    def __post_init__(self) -> None:
        for field_name in MAPPER_FIELDS:
            value = getattr(self, field_name)
            normalized = "" if value is None else str(value).strip()
            object.__setattr__(self, field_name, normalized)

        if not self.timestamp:
            object.__setattr__(self, "timestamp", _current_timestamp())

        validate_mapper_record(self)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def create_mapper_record(**values: Any) -> MapperRecord:
    return MapperRecord(**values)


def validate_mapper_record(record: MapperRecord) -> None:
    if not any(getattr(record, field_name) for field_name in MAPPER_CONTENT_FIELDS):
        raise MapperValidationError("Mapper record needs at least one field.")

    missing_fields = [
        field_name
        for field_name in REQUIRED_MAPPER_FIELDS
        if not getattr(record, field_name)
    ]

    if missing_fields:
        names = ", ".join(missing_fields)
        raise MapperValidationError(f"Missing required mapper field(s): {names}")
