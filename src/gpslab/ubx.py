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
