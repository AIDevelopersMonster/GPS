import json
import tempfile
import unittest
from pathlib import Path

from gpslab.registry import add_inspection, build_rinv_text, export_json, list_inspections


class TestRegistry(unittest.TestCase):
    def test_rinv_text_fits_30_bytes(self):
        text = build_rinv_text("GPS6-2026-00001", "2026-10-01T01:23:45Z")
        self.assertEqual(text, "GPS6-2026-00001 20261001 OK")
        self.assertLessEqual(len(text.encode("ascii")), 30)

    def test_add_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "gpslab.sqlite3"
            row = add_inspection(
                payload={"checks": {"uart": "PASS", "nmea": "PASS"}},
                board="GY-GPS6MV2",
                receiver="u-blox 6 - GPS Receiver",
                sw_version="7.03 (45969)",
                hw_version="00040007",
                result="PASS",
                tested_at_utc="2026-10-01T01:23:45Z",
                rinv_before="EMPTY / FACTORY DEFAULT",
                db_path=db,
            )
            self.assertEqual(row["module_code"], "GPS6-2026-00001")
            rows = list_inspections(db_path=db)
            self.assertEqual(len(rows), 1)

            out = Path(tmp) / "export.json"
            export_json(out, db)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data[0]["module_code"], "GPS6-2026-00001")
            self.assertEqual(data[0]["result"], "PASS")


if __name__ == "__main__":
    unittest.main()
