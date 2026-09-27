import unittest

from gpslab.diagnostics import GPSDiagnostics
from gpslab.nmea import nmea_checksum
from gpslab.ubx import build_packet


def sentence(body: str) -> bytes:
    return f"$" + body + f"*{nmea_checksum(body):02X}\r\n"


class TestDiagnostics(unittest.TestCase):
    def test_nmea_state(self):
        diag = GPSDiagnostics(port="COM7", baud=9600)
        diag.feed(
            sentence(
                "GPGGA,123519,4807.038,N,01131.000,E,"
                "1,08,0.9,545.4,M,46.9,M,,"
            ).encode("ascii")
        )
        diag.feed(sentence("GPGSA,A,3,,,,,,,,,,,,,1.8,0.9,1.5").encode("ascii"))

        self.assertEqual(diag.state.protocol, "NMEA")
        self.assertEqual(diag.state.fix, "3D")
        self.assertEqual(diag.state.satellites_used, 8)

    def test_ubx_state(self):
        diag = GPSDiagnostics()
        payload = (
            b"SW 1.00".ljust(30, b"\x00")
            + b"HW 0001".ljust(10, b"\x00")
            + b"MOD=NEO-6M".ljust(30, b"\x00")
        )
        diag.feed(build_packet(0x0A, 0x04, payload))

        self.assertEqual(diag.state.protocol, "UBX")
        self.assertEqual(diag.state.receiver_identity, "NEO-6M")


if __name__ == "__main__":
    unittest.main()
