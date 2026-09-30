import unittest

from gpslab.ubx import (
    CFG_USB_POLL,
    MON_VER_POLL,
    SEC_UNIQID_POLL,
    build_packet,
    extract_frames,
    packet_is_valid,
    parse_cfg_usb,
    parse_mon_ver,
    parse_sec_uniqid,
)


class TestUBX(unittest.TestCase):
    def test_mon_ver_poll(self):
        self.assertEqual(MON_VER_POLL[:2], b"\xB5\x62")
        self.assertEqual(MON_VER_POLL[2:4], b"\x0A\x04")
        self.assertEqual(len(MON_VER_POLL), 8)
        self.assertTrue(packet_is_valid(MON_VER_POLL))

    def test_identity_polls_are_valid(self):
        self.assertTrue(packet_is_valid(CFG_USB_POLL))
        self.assertTrue(packet_is_valid(SEC_UNIQID_POLL))

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

    def test_parse_cfg_usb(self):
        payload = bytearray(108)
        payload[0:2] = (0x1546).to_bytes(2, "little")
        payload[2:4] = (0x01A6).to_bytes(2, "little")
        payload[8:10] = (100).to_bytes(2, "little")
        payload[12:44] = b"u-blox AG".ljust(32, b"\x00")
        payload[44:76] = b"u-blox GNSS receiver".ljust(32, b"\x00")
        payload[76:108] = b"ABC123".ljust(32, b"\x00")
        result = parse_cfg_usb(bytes(payload))
        self.assertEqual(result["vendor_id"], 0x1546)
        self.assertEqual(result["serial_number"], "ABC123")

    def test_parse_sec_uniqid(self):
        payload = b"\x01\x00\x00\x00\x11\x22\x33\x44\x55"
        result = parse_sec_uniqid(payload)
        self.assertEqual(result["version"], 1)
        self.assertEqual(result["unique_id"], "1122334455")


if __name__ == "__main__":
    unittest.main()
