from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pyscout.core.models import MAPPER_FIELDS, MapperRecord


DEFAULT_DATABASE_ENV = "PYSCOUT_DB_PATH"


def default_database_path() -> Path:
    configured_path = os.environ.get(DEFAULT_DATABASE_ENV)
    if configured_path:
        return Path(configured_path)

    return Path.home() / ".pyscout" / "pyscout.db"


def open_default_store() -> SQLiteStore:
    return SQLiteStore(default_database_path())


class SQLiteStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.initialize()

    def initialize(self) -> None:
        parent = self.database_path.parent
        if parent != Path("."):
            parent.mkdir(parents=True, exist_ok=True)

        with self._connection() as connection:
            columns = ", ".join(f"{field_name} TEXT NOT NULL" for field_name in MAPPER_FIELDS)
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS mapper_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    {columns}
                )
                """
            )

    def save_mapper_record(self, record: MapperRecord) -> int:
        placeholders = ", ".join("?" for _ in MAPPER_FIELDS)
        columns = ", ".join(MAPPER_FIELDS)
        values = [getattr(record, field_name) for field_name in MAPPER_FIELDS]

        with self._connection() as connection:
            cursor = connection.execute(
                f"INSERT INTO mapper_records ({columns}) VALUES ({placeholders})",
                values,
            )
            return int(cursor.lastrowid)

    def read_mapper_records(self) -> list[MapperRecord]:
        columns = ", ".join(MAPPER_FIELDS)

        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT {columns} FROM mapper_records ORDER BY id"
            ).fetchall()

        return [
            MapperRecord(
                **{field_name: row[field_name] for field_name in MAPPER_FIELDS}
            )
            for row in rows
        ]

    def read_mapper_record_rows(self) -> list[dict[str, Any]]:
        columns = ", ".join(("id", *MAPPER_FIELDS))

        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT {columns} FROM mapper_records ORDER BY id"
            ).fetchall()

        return [
            {"id": int(row["id"])}
            | {field_name: row[field_name] for field_name in MAPPER_FIELDS}
            for row in rows
        ]

    def update_mapper_record(self, record_id: int, record: MapperRecord) -> bool:
        assignments = ", ".join(f"{field_name} = ?" for field_name in MAPPER_FIELDS)
        values = [getattr(record, field_name) for field_name in MAPPER_FIELDS]

        with self._connection() as connection:
            cursor = connection.execute(
                f"UPDATE mapper_records SET {assignments} WHERE id = ?",
                [*values, record_id],
            )
            return cursor.rowcount > 0

    def delete_mapper_record(self, record_id: int) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM mapper_records WHERE id = ?",
                (record_id,),
            )
            return cursor.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()
