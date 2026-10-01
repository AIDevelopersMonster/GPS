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
NAV_TIMEUTC_POLL = build_packet(0x01, 0x21)
MON_HW_POLL = build_packet(0x0A, 0x09)
MON_IO_POLL = build_packet(0x0A, 0x02)
MON_RXBUF_POLL = build_packet(0x0A, 0x07)
MON_TXBUF_POLL = build_packet(0x0A, 0x08)


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


def parse_nav_timeutc(payload: bytes) -> dict:
    """Parse UBX-NAV-TIMEUTC UTC solution and validity flags."""
    if len(payload) < 20:
        return {}

    valid = payload[19]
    return {
        "itow_ms": int.from_bytes(payload[0:4], "little"),
        "time_accuracy_ns": int.from_bytes(payload[4:8], "little"),
        "nano_ns": int.from_bytes(payload[8:12], "little", signed=True),
        "year": int.from_bytes(payload[12:14], "little"),
        "month": payload[14],
        "day": payload[15],
        "hour": payload[16],
        "minute": payload[17],
        "second": payload[18],
        "valid_flags": valid,
        "valid_tow": bool(valid & 0x01),
        "valid_week": bool(valid & 0x02),
        "valid_utc": bool(valid & 0x04),
    }




PORT_NAMES = {
    0: "DDC/I2C",
    1: "UART1",
    2: "UART2",
    3: "USB",
    4: "SPI",
}


def parse_mon_hw(payload: bytes) -> dict:
    """Parse u-blox MON-HW common fields, including u-blox 6 interference data."""
    if len(payload) < 24:
        return {}

    flags = payload[22]
    antenna_status_code = payload[20]
    antenna_power_code = payload[21]
    antenna_status_names = {
        0: "INIT",
        1: "DONTKNOW",
        2: "OK",
        3: "SHORT",
        4: "OPEN",
    }
    antenna_power_names = {
        0: "OFF",
        1: "ON",
        2: "DONTKNOW",
    }
    jamming_state = (flags >> 2) & 0x03
    jamming_state_names = {
        0: "UNKNOWN / DISABLED",
        1: "OK",
        2: "WARNING",
        3: "CRITICAL",
    }

    jam_ind = None
    if len(payload) >= 68:
        jam_ind = payload[53]
    elif len(payload) >= 60:
        jam_ind = payload[45]

    result = {
        "payload_length": len(payload),
        "pin_sel": int.from_bytes(payload[0:4], "little"),
        "pin_bank": int.from_bytes(payload[4:8], "little"),
        "pin_dir": int.from_bytes(payload[8:12], "little"),
        "pin_val": int.from_bytes(payload[12:16], "little"),
        "noise_per_ms": int.from_bytes(payload[16:18], "little"),
        "agc_cnt": int.from_bytes(payload[18:20], "little"),
        "antenna_status_code": antenna_status_code,
        "antenna_status": antenna_status_names.get(
            antenna_status_code, f"UNKNOWN({antenna_status_code})"
        ),
        "antenna_power_code": antenna_power_code,
        "antenna_power": antenna_power_names.get(
            antenna_power_code, f"UNKNOWN({antenna_power_code})"
        ),
        "flags": flags,
        "rtc_calib": bool(flags & 0x01),
        "safe_boot": bool(flags & 0x02),
        "jamming_state": jamming_state,
        "jamming_state_name": jamming_state_names[jamming_state],
        "used_mask": int.from_bytes(payload[24:28], "little")
        if len(payload) >= 28
        else None,
        "jam_ind": jam_ind,
    }

    if len(payload) >= 68:
        result.update(
            pin_irq=int.from_bytes(payload[56:60], "little"),
            pull_h=int.from_bytes(payload[60:64], "little"),
            pull_l=int.from_bytes(payload[64:68], "little"),
        )
    elif len(payload) >= 60:
        result.update(
            pin_irq=int.from_bytes(payload[48:52], "little"),
            pull_h=int.from_bytes(payload[52:56], "little"),
            pull_l=int.from_bytes(payload[56:60], "little"),
        )

    return result


def parse_mon_io(payload: bytes) -> list[dict]:
    """Parse MON-IO repeated 20-byte port blocks."""
    if len(payload) < 20 or len(payload) % 20:
        return []

    ports = []
    for index in range(len(payload) // 20):
        offset = index * 20
        ports.append(
            {
                "port": index,
                "name": PORT_NAMES.get(index, f"PORT{index}"),
                "rx_bytes": int.from_bytes(payload[offset : offset + 4], "little"),
                "tx_bytes": int.from_bytes(payload[offset + 4 : offset + 8], "little"),
                "parity_errs": int.from_bytes(payload[offset + 8 : offset + 10], "little"),
                "framing_errs": int.from_bytes(payload[offset + 10 : offset + 12], "little"),
                "overrun_errs": int.from_bytes(payload[offset + 12 : offset + 14], "little"),
                "break_cond": int.from_bytes(payload[offset + 14 : offset + 16], "little"),
                "rx_busy": bool(payload[offset + 16]),
                "tx_busy": bool(payload[offset + 17]),
            }
        )
    return ports


def parse_mon_rxbuf(payload: bytes) -> list[dict]:
    """Parse MON-RXBUF six target buffer entries."""
    if len(payload) < 24:
        return []

    rows = []
    for index in range(6):
        rows.append(
            {
                "target": index,
                "name": PORT_NAMES.get(index, f"TARGET{index}"),
                "pending": int.from_bytes(payload[index * 2 : index * 2 + 2], "little"),
                "usage": payload[12 + index],
                "peak_usage": payload[18 + index],
            }
        )
    return rows


def parse_mon_txbuf(payload: bytes) -> dict:
    """Parse MON-TXBUF six target entries and aggregate status."""
    if len(payload) < 28:
        return {}

    rows = []
    for index in range(6):
        rows.append(
            {
                "target": index,
                "name": PORT_NAMES.get(index, f"TARGET{index}"),
                "pending": int.from_bytes(payload[index * 2 : index * 2 + 2], "little"),
                "usage": payload[12 + index],
                "peak_usage": payload[18 + index],
            }
        )

    errors = payload[26]
    return {
        "targets": rows,
        "total_usage": payload[24],
        "total_peak_usage": payload[25],
        "errors": errors,
        "limit_reached": bool(errors & 0x01),
        "memory_allocation_error": bool(errors & 0x02),
        "allocation_error": bool(errors & 0x04),
    }


def frame_name(msg_class: int, msg_id: int) -> str:
    names = {
        (0x0A, 0x04): "MON-VER",
        (0x06, 0x1B): "CFG-USB",
        (0x27, 0x03): "SEC-UNIQID",
        (0x01, 0x21): "NAV-TIMEUTC",
        (0x0A, 0x09): "MON-HW",
        (0x0A, 0x02): "MON-IO",
        (0x0A, 0x07): "MON-RXBUF",
        (0x0A, 0x08): "MON-TXBUF",
        (0x05, 0x00): "ACK-NAK",
        (0x05, 0x01): "ACK-ACK",
    }
    return names.get((msg_class, msg_id), f"{msg_class:02X}/{msg_id:02X}")
