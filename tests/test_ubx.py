import unittest

from gpslab.ubx import (
    CFG_USB_POLL,
    MON_VER_POLL,
    SEC_UNIQID_POLL,
    MON_HW_POLL,
    MON_IO_POLL,
    MON_RXBUF_POLL,
    MON_TXBUF_POLL,
    build_packet,
    extract_frames,
    packet_is_valid,
    parse_cfg_usb,
    parse_mon_hw,
    parse_mon_io,
    parse_mon_rxbuf,
    parse_mon_txbuf,
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

    def test_engineering_polls_are_valid(self):
        for packet in (MON_HW_POLL, MON_IO_POLL, MON_RXBUF_POLL, MON_TXBUF_POLL):
            self.assertTrue(packet_is_valid(packet))

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

    def test_parse_mon_hw(self):
        payload = bytearray(68)
        payload[16:18] = (42).to_bytes(2, "little")
        payload[18:20] = (8192).to_bytes(2, "little")
        payload[20] = 2
        payload[21] = 1
        payload[22] = 0x0D
        payload[53] = 77
        result = parse_mon_hw(bytes(payload))
        self.assertEqual(result["noise_per_ms"], 42)
        self.assertEqual(result["agc_cnt"], 8192)
        self.assertEqual(result["antenna_status"], "OK")
        self.assertEqual(result["jamming_state_name"], "CRITICAL")
        self.assertEqual(result["jam_ind"], 77)

    def test_parse_mon_io(self):
        payload = bytearray(20)
        payload[0:4] = (123).to_bytes(4, "little")
        payload[4:8] = (456).to_bytes(4, "little")
        payload[8:10] = (2).to_bytes(2, "little")
        payload[16] = 1
        rows = parse_mon_io(bytes(payload))
        self.assertEqual(rows[0]["rx_bytes"], 123)
        self.assertEqual(rows[0]["tx_bytes"], 456)
        self.assertEqual(rows[0]["parity_errs"], 2)
        self.assertTrue(rows[0]["rx_busy"])

    def test_parse_mon_buffers(self):
        rx = bytearray(24)
        rx[0:2] = (12).to_bytes(2, "little")
        rx[12] = 30
        rx[18] = 50
        rx_rows = parse_mon_rxbuf(bytes(rx))
        self.assertEqual(rx_rows[0]["pending"], 12)
        self.assertEqual(rx_rows[0]["usage"], 30)
        self.assertEqual(rx_rows[0]["peak_usage"], 50)

        tx = bytearray(28)
        tx[0:2] = (7).to_bytes(2, "little")
        tx[12] = 10
        tx[18] = 20
        tx[24] = 15
        tx[25] = 25
        tx[26] = 1
        tx_info = parse_mon_txbuf(bytes(tx))
        self.assertEqual(tx_info["targets"][0]["pending"], 7)
        self.assertTrue(tx_info["limit_reached"])


if __name__ == "__main__":
    unittest.main()
