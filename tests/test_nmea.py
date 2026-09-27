import unittest

from gpslab.nmea import decode_fields, nmea_checksum, parse_sentence


def sentence(body: str) -> str:
    return f"$" + body + f"*{nmea_checksum(body):02X}"


class TestNMEA(unittest.TestCase):
    def test_known_gga(self):
        raw = (
            "$GPGGA,123519,4807.038,N,01131.000,E,1,08,"
            "0.9,545.4,M,46.9,M,,*47"
        )
        parsed = parse_sentence(raw)
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed.checksum_ok)
        self.assertEqual(parsed.message_type, "GGA")

        values = decode_fields(parsed)
        self.assertEqual(values["satellites_used"], 8)
        self.assertAlmostEqual(values["latitude"], 48.1173, places=4)
        self.assertAlmostEqual(values["longitude"], 11.5166667, places=4)
        self.assertAlmostEqual(values["altitude_m"], 545.4)

    def test_bad_checksum(self):
        parsed = parse_sentence("$GPGGA,1,2,3*00")
        self.assertIsNotNone(parsed)
        self.assertFalse(parsed.checksum_ok)


if __name__ == "__main__":
    unittest.main()
