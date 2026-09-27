from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class NMEASentence:
    raw: str
    talker: str
    message_type: str
    fields: list[str]
    checksum_ok: bool


def nmea_checksum(body: str) -> int:
    value = 0
    for char in body:
        value ^= ord(char)
    return value


def parse_sentence(line: str) -> Optional[NMEASentence]:
    line = line.strip()
    if not line.startswith("$"):
        return None

    payload = line[1:]
    supplied_checksum = None
    if "*" in payload:
        body, checksum_text = payload.rsplit("*", 1)
        if len(checksum_text) < 2:
            return NMEASentence(line, "", "", [], False)
        try:
            supplied_checksum = int(checksum_text[:2], 16)
        except ValueError:
            return NMEASentence(line, "", "", [], False)
    else:
        body = payload

    parts = body.split(",")
    if not parts or len(parts[0]) < 3:
        return NMEASentence(line, "", "", [], False)

    sentence_id = parts[0]
    talker = sentence_id[:-3]
    message_type = sentence_id[-3:]
    fields = parts[1:]

    checksum_ok = (
        supplied_checksum is not None
        and nmea_checksum(body) == supplied_checksum
    )

    return NMEASentence(
        raw=line,
        talker=talker,
        message_type=message_type,
        fields=fields,
        checksum_ok=checksum_ok,
    )


def _safe_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_coordinate(value: str, hemisphere: str) -> Optional[float]:
    if not value or not hemisphere:
        return None

    try:
        raw = float(value)
    except ValueError:
        return None

    degrees = int(raw // 100)
    minutes = raw - degrees * 100
    decimal = degrees + minutes / 60.0

    if hemisphere.upper() in ("S", "W"):
        decimal = -decimal

    return decimal


def decode_fields(sentence: NMEASentence) -> dict:
    f = sentence.fields
    message = sentence.message_type
    result: dict = {"message_type": message, "talker": sentence.talker}

    if message == "GGA":
        if len(f) >= 9:
            result.update(
                utc_time=f[0] or None,
                latitude=parse_coordinate(f[1], f[2]),
                longitude=parse_coordinate(f[3], f[4]),
                fix_quality=_safe_int(f[5]),
                satellites_used=_safe_int(f[6]),
                hdop=_safe_float(f[7]),
                altitude_m=_safe_float(f[8]),
            )

    elif message == "RMC":
        if len(f) >= 9:
            result.update(
                utc_time=f[0] or None,
                navigation_status=f[1] or None,
                latitude=parse_coordinate(f[2], f[3]),
                longitude=parse_coordinate(f[4], f[5]),
                speed_knots=_safe_float(f[6]),
                utc_date=f[8] or None,
            )

    elif message == "GSA":
        if len(f) >= 2:
            result["fix_type"] = _safe_int(f[1])
        if len(f) >= 17:
            result["hdop"] = _safe_float(f[-2])

    elif message == "GSV":
        if len(f) >= 3:
            result["satellites_visible"] = _safe_int(f[2])

    elif message == "VTG":
        if len(f) >= 7:
            result["speed_knots"] = _safe_float(f[4])
            result["speed_kmh"] = _safe_float(f[6])

    elif message == "TXT":
        if len(f) >= 4:
            result["text"] = f[3]

    return result
