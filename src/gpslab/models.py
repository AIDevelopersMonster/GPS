from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class GPSState:
    port: Optional[str] = None
    baud: Optional[int] = None

    bytes_received: int = 0
    nmea_valid: int = 0
    nmea_invalid: int = 0
    ubx_frames: int = 0

    protocol: str = "NONE"
    last_sentence: Optional[str] = None
    sentence_counts: dict[str, int] = field(default_factory=dict)

    fix: str = "NO FIX"
    fix_quality: int = 0
    fix_type: int = 1
    navigation_status: Optional[str] = None

    satellites_used: Optional[int] = None
    satellites_visible: Optional[int] = None
    hdop: Optional[float] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None
    speed_knots: Optional[float] = None
    speed_kmh: Optional[float] = None

    utc_time: Optional[str] = None
    utc_date: Optional[str] = None
    gga_rate_hz: Optional[float] = None

    ubx_sw_version: Optional[str] = None
    ubx_hw_version: Optional[str] = None
    ubx_extensions: list[str] = field(default_factory=list)

    usb_vendor_id: Optional[int] = None
    usb_product_id: Optional[int] = None
    usb_power_consumption_ma: Optional[int] = None
    usb_flags: Optional[int] = None
    usb_vendor_string: Optional[str] = None
    usb_product_string: Optional[str] = None
    usb_serial_number: Optional[str] = None

    unique_id: Optional[str] = None
    unique_id_version: Optional[int] = None

    @property
    def has_data(self) -> bool:
        return self.bytes_received > 0

    @property
    def has_protocol(self) -> bool:
        return self.nmea_valid > 0 or self.ubx_frames > 0

    @property
    def protocol_version(self) -> Optional[str]:
        for item in self.ubx_extensions:
            if item.startswith("PROTVER="):
                return item.split("=", 1)[1].strip() or None
        return None

    @property
    def receiver_identity(self) -> Optional[str]:
        for item in self.ubx_extensions:
            if item.startswith("MOD="):
                return item[4:].strip() or None
        if self.usb_product_string:
            return self.usb_product_string
        if self.ubx_sw_version or self.ubx_hw_version:
            return "u-blox compatible receiver"
        return None

    def update_protocol(self) -> None:
        has_nmea = self.nmea_valid > 0
        has_ubx = self.ubx_frames > 0
        if has_nmea and has_ubx:
            self.protocol = "NMEA + UBX"
        elif has_nmea:
            self.protocol = "NMEA"
        elif has_ubx:
            self.protocol = "UBX"
        elif self.has_data:
            self.protocol = "RAW / UNKNOWN"
        else:
            self.protocol = "NONE"

    def update_fix(self) -> None:
        if self.fix_type >= 3:
            self.fix = "3D"
        elif self.fix_type == 2:
            self.fix = "2D"
        elif self.fix_quality > 0:
            self.fix = "FIX"
        else:
            self.fix = "NO FIX"

    def to_dict(self) -> dict:
        result = asdict(self)
        result["receiver_identity"] = self.receiver_identity
        result["protocol_version"] = self.protocol_version
        return result
