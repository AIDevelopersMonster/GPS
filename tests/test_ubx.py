import unittest

from gpslab.ubx import MON_VER_POLL, build_packet, extract_frames, parse_mon_ver


class TestUBX(unittest.TestCase):
    def test_mon_ver_poll(self):
        self.assertEqual(MON_VER_POLL[:2], b"\xB5\x62")
        self.assertEqual(MON_VER_POLL[2:4], b"\x0A\x04")
        self.assertEqual(len(MON_VER_POLL), 8)

    def test_extract_frame(self):
        packet = build_packet(0x01, 0x02, b"\x10\x20\x30")
        buffer = bytearray(b"noise" + packet)
        frames = extract_frames(buffer)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].payload, b"\x10\x20\x30")

    def test_parse_mon_ver(self):
        sw = b"SW 1.00".ljust(30, b"\x00")
        hw = b"HW 0001".ljust(10, b"\x00")
        ext = b"MOD=NEO-6M".ljust(30, b"\x00")
        result = parse_mon_ver(sw + hw + ext)
        self.assertEqual(result["sw_version"], "SW 1.00")
        self.assertEqual(result["hw_version"], "HW 0001")
        self.assertIn("MOD=NEO-6M", result["extensions"])


if __name__ == "__main__":
    unittest.main()
