from __future__ import annotations

import time
from collections import deque

from .models import GPSState
from .nmea import decode_fields, parse_sentence
from .ubx import (
    extract_frames,
    parse_cfg_rinv,
    parse_cfg_usb,
    parse_mon_hw,
    parse_mon_io,
    parse_mon_rxbuf,
    parse_mon_txbuf,
    parse_mon_ver,
    parse_nav_timeutc,
    parse_sec_uniqid,
)


class GPSDiagnostics:
    def __init__(self, port: str | None = None, baud: int | None = None):
        self.state = GPSState(port=port, baud=baud)
        self._line_buffer = bytearray()
        self._ubx_buffer = bytearray()
        self._gga_times: deque[float] = deque(maxlen=8)

    def feed(self, data: bytes) -> GPSState:
        if not data:
            return self.state

        self.state.bytes_received += len(data)
        self._line_buffer.extend(data)
        self._ubx_buffer.extend(data)

        self._consume_nmea()
        self._consume_ubx()

        self.state.update_protocol()
        self.state.update_fix()
        return self.state

    def _consume_nmea(self) -> None:
        while b"\n" in self._line_buffer:
            raw_line, _, remainder = self._line_buffer.partition(b"\n")
            self._line_buffer[:] = remainder

            dollar = raw_line.rfind(b"$")
            if dollar < 0:
                continue

            text = raw_line[dollar:].decode("ascii", "replace").strip()
            sentence = parse_sentence(text)
            if sentence is None:
                continue

            if not sentence.checksum_ok:
                self.state.nmea_invalid += 1
                continue

            self.state.nmea_valid += 1
            self.state.last_sentence = sentence.message_type
            self.state.latest_nmea_raw[sentence.message_type] = sentence.raw
            self.state.sentence_counts[sentence.message_type] = (
                self.state.sentence_counts.get(sentence.message_type, 0) + 1
            )

            values = decode_fields(sentence)
            self._apply_values(values)

            if sentence.message_type == "GGA":
                now = time.monotonic()
                self._gga_times.append(now)
                if len(self._gga_times) >= 2:
                    span = self._gga_times[-1] - self._gga_times[0]
                    if span > 0:
                        self.state.gga_rate_hz = (
                            len(self._gga_times) - 1
                        ) / span

    def _consume_ubx(self) -> None:
        for frame in extract_frames(self._ubx_buffer):
            self.state.ubx_frames += 1

            if frame.msg_class == 0x0A and frame.msg_id == 0x04:
                info = parse_mon_ver(frame.payload)
                if info:
                    self.state.ubx_sw_version = info.get("sw_version")
                    self.state.ubx_hw_version = info.get("hw_version")
                    self.state.ubx_extensions = info.get("extensions", [])

            elif frame.msg_class == 0x06 and frame.msg_id == 0x1B:
                info = parse_cfg_usb(frame.payload)
                if info:
                    self.state.usb_vendor_id = info.get("vendor_id")
                    self.state.usb_product_id = info.get("product_id")
                    self.state.usb_power_consumption_ma = info.get("power_consumption_ma")
                    self.state.usb_flags = info.get("flags")
                    self.state.usb_vendor_string = info.get("vendor_string")
                    self.state.usb_product_string = info.get("product_string")
                    self.state.usb_serial_number = info.get("serial_number")

            elif frame.msg_class == 0x06 and frame.msg_id == 0x34:
                info = parse_cfg_rinv(frame.payload)
                if info:
                    self.state.rinv_flags = info.get("flags")
                    self.state.rinv_dump = info.get("dump")
                    self.state.rinv_binary = info.get("binary")
                    self.state.rinv_data = info.get("data", b"")
                    self.state.rinv_text = info.get("text")
                    self.state.rinv_hex = info.get("hex")
                    self.state.rinv_is_default_empty = info.get("is_default_empty")

            elif frame.msg_class == 0x27 and frame.msg_id == 0x03:
                info = parse_sec_uniqid(frame.payload)
                if info:
                    self.state.unique_id_version = info.get("version")
                    self.state.unique_id = info.get("unique_id")

            elif frame.msg_class == 0x01 and frame.msg_id == 0x21:
                info = parse_nav_timeutc(frame.payload)
                if info:
                    self.state.ubx_utc_itow_ms = info.get("itow_ms")
                    self.state.ubx_utc_time_accuracy_ns = info.get("time_accuracy_ns")
                    self.state.ubx_utc_nano_ns = info.get("nano_ns")
                    self.state.ubx_utc_year = info.get("year")
                    self.state.ubx_utc_month = info.get("month")
                    self.state.ubx_utc_day = info.get("day")
                    self.state.ubx_utc_hour = info.get("hour")
                    self.state.ubx_utc_minute = info.get("minute")
                    self.state.ubx_utc_second = info.get("second")
                    self.state.ubx_utc_valid_flags = info.get("valid_flags")
                    self.state.ubx_utc_valid_tow = info.get("valid_tow")
                    self.state.ubx_utc_valid_week = info.get("valid_week")
                    self.state.ubx_utc_valid = info.get("valid_utc")

            elif frame.msg_class == 0x0A and frame.msg_id == 0x09:
                info = parse_mon_hw(frame.payload)
                if info:
                    self.state.mon_hw = info

            elif frame.msg_class == 0x0A and frame.msg_id == 0x02:
                info = parse_mon_io(frame.payload)
                if info:
                    self.state.mon_io = info

            elif frame.msg_class == 0x0A and frame.msg_id == 0x07:
                info = parse_mon_rxbuf(frame.payload)
                if info:
                    self.state.mon_rxbuf = info

            elif frame.msg_class == 0x0A and frame.msg_id == 0x08:
                info = parse_mon_txbuf(frame.payload)
                if info:
                    self.state.mon_txbuf = info

    def _apply_values(self, values: dict) -> None:
        for key in (
            "utc_time",
            "utc_date",
            "navigation_status",
            "latitude",
            "longitude",
            "altitude_m",
            "hdop",
            "speed_knots",
            "speed_kmh",
            "satellites_used",
            "satellites_visible",
            "fix_quality",
            "fix_type",
        ):
            value = values.get(key)
            if value is not None:
                setattr(self.state, key, value)
