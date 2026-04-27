from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyscout.core.mapper_service import MapperService, mapper_values_from_discovery
from pyscout.storage.sqlite_store import SQLiteStore


class MapperServiceTests(unittest.TestCase):
    def test_discovery_result_saves_mapper_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteStore(Path(tmpdir) / "pyscout.db")
            service = MapperService(store)

            record_id = service.save_discovery_result(
                {
                    "switch_name": "sw-core-1",
                    "switch_port": "Gi1/0/12",
                    "neighbor_ip": "10.0.0.1",
                    "protocol": "LLDP",
                    "local_adapter": "Ethernet",
                    "timestamp": "2026-04-27T09:00:00-04:00",
                }
            )
            rows = service.read_rows()

        self.assertEqual(record_id, 1)
        self.assertEqual(rows[0]["switch"], "sw-core-1")
        self.assertEqual(rows[0]["switch_port"], "Gi1/0/12")
        self.assertEqual(rows[0]["neighbor_ip"], "10.0.0.1")
        self.assertIn("LLDP discovery", rows[0]["note"])

    def test_mapper_values_from_discovery_maps_only_core_fields(self) -> None:
        values = mapper_values_from_discovery(
            {
                "switch_name": "sw-access-2",
                "switch_port": "Te1/1/1",
                "neighbor_ip": "10.0.0.2",
                "protocol": "CDP",
            }
        )

        self.assertEqual(values["switch"], "sw-access-2")
        self.assertEqual(values["switch_port"], "Te1/1/1")
        self.assertEqual(values["neighbor_ip"], "10.0.0.2")
        self.assertEqual(values["note"], "CDP discovery")


if __name__ == "__main__":
    unittest.main()
