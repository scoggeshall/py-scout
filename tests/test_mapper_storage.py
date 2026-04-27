from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyscout.core.models import MapperRecord, MapperValidationError
from pyscout.storage.sqlite_store import SQLiteStore


class MapperStorageTests(unittest.TestCase):
    def test_create_mapper_record(self) -> None:
        record = MapperRecord(
            site="HQ",
            building="Main",
            floor="2",
            room="201",
            wall_jack="A-12",
            patch_panel="PP-1",
            switch="sw-core-1",
            switch_port="Gi1/0/12",
            mac="00:11:22:33:44:55",
            vendor="CIMSYS Inc",
            hostname="printer-201",
            neighbor_ip="192.168.10.2",
            note="North wall",
        )

        self.assertEqual(record.site, "HQ")
        self.assertEqual(record.wall_jack, "A-12")
        self.assertTrue(record.timestamp)

    def test_mapper_record_allows_partial_discovery_records(self) -> None:
        record = MapperRecord(switch="sw-core-1", switch_port="Gi1/0/12")

        self.assertEqual(record.switch, "sw-core-1")
        self.assertEqual(record.switch_port, "Gi1/0/12")

    def test_mapper_record_rejects_empty_records(self) -> None:
        with self.assertRaises(MapperValidationError):
            MapperRecord()

    def test_save_and_read_mapper_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = Path(tmpdir) / "pyscout.db"
            store = SQLiteStore(database_path)
            record = MapperRecord(
                site="HQ",
                building="Main",
                floor="2",
                room="201",
                wall_jack="A-12",
                switch="sw-core-1",
                switch_port="Gi1/0/12",
            )

            record_id = store.save_mapper_record(record)
            records = store.read_mapper_records()

        self.assertEqual(record_id, 1)
        self.assertEqual(records, [record])

    def test_mapper_record_rows_include_stable_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = Path(tmpdir) / "pyscout.db"
            store = SQLiteStore(database_path)

            first_id = store.save_mapper_record(
                MapperRecord(site="HQ", wall_jack="A-12")
            )
            second_id = store.save_mapper_record(
                MapperRecord(site="HQ", wall_jack="A-13")
            )
            rows = store.read_mapper_record_rows()

        self.assertEqual([row["id"] for row in rows], [first_id, second_id])
        self.assertEqual(rows[0]["site"], "HQ")
        self.assertEqual(rows[1]["wall_jack"], "A-13")

    def test_update_mapper_record_persists_to_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = Path(tmpdir) / "pyscout.db"
            store = SQLiteStore(database_path)
            record_id = store.save_mapper_record(
                MapperRecord(site="HQ", wall_jack="A-12", room="201")
            )

            updated = store.update_mapper_record(
                record_id,
                MapperRecord(site="HQ", wall_jack="A-12", room="214"),
            )
            rows = store.read_mapper_record_rows()

        self.assertTrue(updated)
        self.assertEqual(rows[0]["id"], record_id)
        self.assertEqual(rows[0]["room"], "214")

    def test_delete_mapper_record_removes_from_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = Path(tmpdir) / "pyscout.db"
            store = SQLiteStore(database_path)
            first_id = store.save_mapper_record(
                MapperRecord(site="HQ", wall_jack="A-12")
            )
            second_id = store.save_mapper_record(
                MapperRecord(site="HQ", wall_jack="A-13")
            )

            deleted = store.delete_mapper_record(first_id)
            rows = store.read_mapper_record_rows()

        self.assertTrue(deleted)
        self.assertEqual([row["id"] for row in rows], [second_id])

    def test_missing_database_creates_new_database_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = Path(tmpdir) / "missing" / "pyscout.db"

            self.assertFalse(database_path.exists())
            store = SQLiteStore(database_path)

            self.assertTrue(database_path.exists())
            self.assertEqual(store.read_mapper_records(), [])


if __name__ == "__main__":
    unittest.main()
