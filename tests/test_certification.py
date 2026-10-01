import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from gpslab.certification import (
    RINVPassRecord,
    build_rinv_record,
    canonical_json,
    create_signed_receipt,
    make_core,
    module_id_text,
    public_key_fingerprint,
    save_receipt,
    station_key_id,
    verify_receipt,
)


class TestCertification(unittest.TestCase):
    def test_rinv_record_roundtrip(self):
        record = RINVPassRecord(
            module_id=bytes.fromhex("0011223344556677"),
            tested_at_unix=1790812800,
            station_key_id=bytes.fromhex("A1B2C3D4"),
            receipt_hash_prefix=bytes.fromhex("00112233445566778899"),
        )
        packed = record.pack()
        self.assertEqual(len(packed), 30)
        parsed = RINVPassRecord.unpack(packed)
        self.assertEqual(parsed, record)
        self.assertEqual(module_id_text(parsed.module_id), "GPS6-0011-2233-4455-6677")

    def test_signed_receipt_verifies(self):
        private = Ed25519PrivateKey.generate()
        public = private.public_key()
        module_id = bytes.fromhex("0011223344556677")
        core = make_core(
            module_id=module_id,
            tested_at_utc="2026-10-01T01:30:00Z",
            station_name="GPS Lab",
            station_public_key_sha256=public_key_fingerprint(public),
            profile="NEO6M-LAB-01",
            receiver={"family": "u-blox 6", "sw": "7.03", "hw": "00040007"},
            checks=[
                {"id": "uart", "pass": True},
                {"id": "nmea", "pass": True},
                {"id": "ubx", "pass": True},
            ],
            measurements={"baud": 9600},
        )
        rinv = build_rinv_record(core, public)
        receipt = create_signed_receipt(
            core=core,
            rinv=rinv,
            write_evidence={
                "rinv_before": "EMPTY / FACTORY DEFAULT",
                "rinv_after_hex": rinv.pack().hex().upper(),
                "saved_to": "EEPROM",
                "readback_match": True,
                "power_cycle_verified": True,
            },
            private_key=private,
            public_key=public,
        )
        result = verify_receipt(receipt, public)
        self.assertTrue(result["valid"])
        self.assertEqual(result["module_id"], "GPS6-0011-2233-4455-6677")

    def test_receipt_tamper_fails(self):
        private = Ed25519PrivateKey.generate()
        public = private.public_key()
        module_id = bytes.fromhex("8899AABBCCDDEEFF")
        core = make_core(
            module_id=module_id,
            tested_at_utc="2026-10-01T01:30:00Z",
            station_name="GPS Lab",
            station_public_key_sha256=public_key_fingerprint(public),
            profile="NEO6M-LAB-01",
            receiver={"family": "u-blox 6"},
            checks=[{"id": "uart", "pass": True}],
            measurements={},
        )
        rinv = build_rinv_record(core, public)
        receipt = create_signed_receipt(
            core=core,
            rinv=rinv,
            write_evidence={"readback_match": True},
            private_key=private,
            public_key=public,
        )
        receipt["core"]["test"]["profile"] = "tampered"
        with self.assertRaises(Exception):
            verify_receipt(receipt, public)


if __name__ == "__main__":
    unittest.main()
