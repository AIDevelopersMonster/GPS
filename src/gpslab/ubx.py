from __future__ import annotations

from dataclasses import dataclass


SYNC = b"\xB5\x62"


@dataclass
class UBXFrame:
    msg_class: int
    msg_id: int
    payload: bytes


def checksum(data: bytes) -> tuple[int, int]:
    ck_a = 0
    ck_b = 0
    for byte in data:
        ck_a = (ck_a + byte) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    return ck_a, ck_b


def build_packet(msg_class: int, msg_id: int, payload: bytes = b"") -> bytes:
    header = bytes(
        [
            msg_class & 0xFF,
            msg_id & 0xFF,
            len(payload) & 0xFF,
            (len(payload) >> 8) & 0xFF,
        ]
    )
    ck_a, ck_b = checksum(header + payload)
    return SYNC + header + payload + bytes([ck_a, ck_b])


MON_VER_POLL = build_packet(0x0A, 0x04)
CFG_USB_POLL = build_packet(0x06, 0x1B)
SEC_UNIQID_POLL = build_packet(0x27, 0x03)


def packet_is_valid(packet: bytes) -> bool:
    if len(packet) < 8 or packet[:2] != SYNC:
        return False

    payload_len = packet[4] | (packet[5] << 8)
    if len(packet) != 8 + payload_len:
        return False

    expected_a, expected_b = checksum(packet[2:-2])
    return packet[-2:] == bytes([expected_a, expected_b])


def extract_frames(buffer: bytearray) -> list[UBXFrame]:
    frames: list[UBXFrame] = []

    while True:
        start = buffer.find(SYNC)
        if start < 0:
            if len(buffer) > 1:
                del buffer[:-1]
            break

        if start > 0:
            del buffer[:start]

        if len(buffer) < 8:
            break

        msg_class = buffer[2]
        msg_id = buffer[3]
        payload_len = buffer[4] | (buffer[5] << 8)
        total = 6 + payload_len + 2

        if len(buffer) < total:
            break

        frame_data = bytes(buffer[2 : 6 + payload_len])
        expected_a, expected_b = checksum(frame_data)
        actual_a = buffer[6 + payload_len]
        actual_b = buffer[7 + payload_len]

        if (expected_a, expected_b) == (actual_a, actual_b):
            payload = bytes(buffer[6 : 6 + payload_len])
            frames.append(UBXFrame(msg_class, msg_id, payload))
            del buffer[:total]
        else:
            del buffer[:2]

    return frames


def parse_mon_ver(payload: bytes) -> dict:
    if len(payload) < 40:
        return {}

    sw = payload[:30].split(b"\x00", 1)[0].decode("ascii", "replace").strip()
    hw = payload[30:40].split(b"\x00", 1)[0].decode("ascii", "replace").strip()

    extensions: list[str] = []
    offset = 40
    while offset + 30 <= len(payload):
        item = (
            payload[offset : offset + 30]
            .split(b"\x00", 1)[0]
            .decode("ascii", "replace")
            .strip()
        )
        if item:
            extensions.append(item)
        offset += 30

    return {
        "sw_version": sw or None,
        "hw_version": hw or None,
        "extensions": extensions,
    }


def _cstring(data: bytes) -> str | None:
    value = data.split(b"\x00", 1)[0].decode("ascii", "replace").strip()
    return value or None


def parse_cfg_usb(payload: bytes) -> dict:
    """Parse the 108-byte UBX-CFG-USB response."""
    if len(payload) < 108:
        return {}

    return {
        "vendor_id": int.from_bytes(payload[0:2], "little"),
        "product_id": int.from_bytes(payload[2:4], "little"),
        "power_consumption_ma": int.from_bytes(payload[8:10], "little"),
        "flags": int.from_bytes(payload[10:12], "little"),
        "vendor_string": _cstring(payload[12:44]),
        "product_string": _cstring(payload[44:76]),
        "serial_number": _cstring(payload[76:108]),
    }


def parse_sec_uniqid(payload: bytes) -> dict:
    """Parse UBX-SEC-UNIQID on receiver generations that implement it."""
    if len(payload) < 9:
        return {}

    unique = payload[4:]
    return {
        "version": payload[0],
        "unique_id": unique.hex().upper() or None,
    }


def frame_name(msg_class: int, msg_id: int) -> str:
    names = {
        (0x0A, 0x04): "MON-VER",
        (0x06, 0x1B): "CFG-USB",
        (0x27, 0x03): "SEC-UNIQID",
        (0x05, 0x00): "ACK-NAK",
        (0x05, 0x01): "ACK-ACK",
    }
    return names.get((msg_class, msg_id), f"{msg_class:02X}/{msg_id:02X}")
