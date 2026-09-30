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


MESSAGE_SUMMARIES = {
    "GGA": "Fix Data / координаты, качество Fix, спутники, HDOP и высота",
    "RMC": "Recommended Minimum / время, дата, статус навигации, координаты, скорость и курс",
    "GSA": "DOP and Active Satellites / тип Fix, используемые спутники и DOP",
    "GSV": "Satellites in View / видимые спутники, высота, азимут и SNR",
    "GLL": "Geographic Position / координаты, UTC и статус",
    "VTG": "Track and Ground Speed / курс и скорость относительно земли",
    "TXT": "Text Transmission / служебное текстовое сообщение приемника",
}


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


def _format_utc(value: str) -> str:
    if not value or len(value) < 6:
        return "-"
    try:
        hour = int(value[0:2])
        minute = int(value[2:4])
        second = float(value[4:])
        return f"{hour:02d}:{minute:02d}:{second:06.3f} UTC"
    except ValueError:
        return value


def _format_date(value: str) -> str:
    if not value or len(value) != 6:
        return "-"
    try:
        day = int(value[0:2])
        month = int(value[2:4])
        year2 = int(value[4:6])
        year = 2000 + year2 if year2 < 80 else 1900 + year2
        return f"{day:02d}.{month:02d}.{year:04d}"
    except ValueError:
        return value


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
                course_deg=_safe_float(f[7]),
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

    elif message == "GLL":
        if len(f) >= 6:
            result.update(
                latitude=parse_coordinate(f[0], f[1]),
                longitude=parse_coordinate(f[2], f[3]),
                utc_time=f[4] or None,
                navigation_status=f[5] or None,
            )

    elif message == "VTG":
        if len(f) >= 7:
            result["speed_knots"] = _safe_float(f[4])
            result["speed_kmh"] = _safe_float(f[6])

    elif message == "TXT":
        if len(f) >= 4:
            result["text"] = f[3]

    return result


def explain_sentence(sentence: NMEASentence) -> dict:
    """Return field-by-field interpretation for the GUI NMEA decoder."""
    f = sentence.fields
    rows: list[dict[str, str]] = []

    def raw(index: int) -> str:
        return f[index] if index < len(f) and f[index] != "" else "-"

    def add(field: str, index: int, decoded: str, meaning: str) -> None:
        rows.append(
            {
                "field": field,
                "raw": raw(index),
                "decoded": decoded or "-",
                "meaning": meaning,
            }
        )

    message = sentence.message_type

    if message == "GGA":
        lat = parse_coordinate(raw(1) if raw(1) != "-" else "", raw(2) if raw(2) != "-" else "")
        lon = parse_coordinate(raw(3) if raw(3) != "-" else "", raw(4) if raw(4) != "-" else "")
        fix_names = {
            0: "0 = invalid / Fix отсутствует",
            1: "1 = GPS SPS fix",
            2: "2 = DGPS fix",
            6: "6 = estimated / dead reckoning",
        }
        fq = _safe_int(raw(5))
        add("UTC time", 0, _format_utc(raw(0)), "Время UTC от приемника")
        add("Latitude", 1, "-" if lat is None else f"{lat:.7f} deg", "Широта в формате ddmm.mmmm")
        add("N/S", 2, raw(2), "Полушарие широты: N север, S юг")
        add("Longitude", 3, "-" if lon is None else f"{lon:.7f} deg", "Долгота в формате dddmm.mmmm")
        add("E/W", 4, raw(4), "Полушарие долготы: E восток, W запад")
        add("Fix quality", 5, fix_names.get(fq, raw(5)), "Качество навигационного решения")
        add("Satellites used", 6, raw(6), "Число спутников, используемых в решении")
        add("HDOP", 7, raw(7), "Горизонтальный геометрический фактор точности; меньше лучше")
        add("Altitude", 8, raw(8) + (" m" if raw(8) != "-" else ""), "Высота над средним уровнем моря")
        add("Altitude unit", 9, raw(9), "Единица высоты; обычно M = метры")
        add("Geoid separation", 10, raw(10) + (" m" if raw(10) != "-" else ""), "Разность геоида и эллипсоида WGS-84")
        add("Geoid unit", 11, raw(11), "Единица geoid separation")
        add("DGPS age", 12, raw(12), "Возраст дифференциальной коррекции, секунд")
        add("DGPS station", 13, raw(13), "ID станции дифференциальных поправок")

    elif message == "RMC":
        lat = parse_coordinate(raw(2) if raw(2) != "-" else "", raw(3) if raw(3) != "-" else "")
        lon = parse_coordinate(raw(4) if raw(4) != "-" else "", raw(5) if raw(5) != "-" else "")
        status = {"A": "A = valid / данные действительны", "V": "V = void / навигационные данные недействительны"}
        speed = _safe_float(raw(6))
        add("UTC time", 0, _format_utc(raw(0)), "Время UTC")
        add("Status", 1, status.get(raw(1), raw(1)), "Статус навигационных данных RMC")
        add("Latitude", 2, "-" if lat is None else f"{lat:.7f} deg", "Широта")
        add("N/S", 3, raw(3), "Полушарие широты")
        add("Longitude", 4, "-" if lon is None else f"{lon:.7f} deg", "Долгота")
        add("E/W", 5, raw(5), "Полушарие долготы")
        add("Speed", 6, "-" if speed is None else f"{speed:.3f} kn / {speed * 1.852:.3f} km/h", "Скорость относительно земли")
        add("Course", 7, raw(7) + (" deg" if raw(7) != "-" else ""), "Истинный курс относительно земли")
        add("Date", 8, _format_date(raw(8)), "Дата UTC в формате ddmmyy")
        add("Mag variation", 9, raw(9), "Магнитное склонение, если передается")
        add("Mag E/W", 10, raw(10), "Направление магнитного склонения")
        add("Mode", 11, raw(11), "Индикатор режима навигации, если поддерживается")

    elif message == "GSA":
        mode = {"A": "A = automatic", "M": "M = manual"}
        fix = {"1": "1 = NO FIX", "2": "2 = 2D FIX", "3": "3 = 3D FIX"}
        add("Selection mode", 0, mode.get(raw(0), raw(0)), "Автоматический или ручной выбор спутников")
        add("Fix type", 1, fix.get(raw(1), raw(1)), "Тип навигационного решения")
        for i in range(12):
            add(f"Satellite PRN {i + 1}", 2 + i, raw(2 + i), "PRN спутника, используемого в решении")
        add("PDOP", 14, raw(14), "Общий геометрический фактор точности")
        add("HDOP", 15, raw(15), "Горизонтальный геометрический фактор точности")
        add("VDOP", 16, raw(16), "Вертикальный геометрический фактор точности")

    elif message == "GSV":
        add("Messages total", 0, raw(0), "Сколько GSV-предложений составляет полный цикл")
        add("Message number", 1, raw(1), "Номер текущей части GSV")
        add("Satellites in view", 2, raw(2), "Общее число видимых спутников")
        block = 0
        index = 3
        while index < len(f):
            block += 1
            add(f"SV{block} PRN", index, raw(index), "Идентификатор спутника")
            add(f"SV{block} elevation", index + 1, raw(index + 1) + (" deg" if raw(index + 1) != "-" else ""), "Высота спутника над горизонтом")
            add(f"SV{block} azimuth", index + 2, raw(index + 2) + (" deg" if raw(index + 2) != "-" else ""), "Азимут спутника")
            add(f"SV{block} SNR", index + 3, raw(index + 3) + (" dB-Hz" if raw(index + 3) != "-" else ""), "Уровень сигнала; пусто означает, что SNR не определен")
            index += 4

    elif message == "GLL":
        lat = parse_coordinate(raw(0) if raw(0) != "-" else "", raw(1) if raw(1) != "-" else "")
        lon = parse_coordinate(raw(2) if raw(2) != "-" else "", raw(3) if raw(3) != "-" else "")
        status = {"A": "A = valid", "V": "V = void"}
        add("Latitude", 0, "-" if lat is None else f"{lat:.7f} deg", "Широта")
        add("N/S", 1, raw(1), "Полушарие широты")
        add("Longitude", 2, "-" if lon is None else f"{lon:.7f} deg", "Долгота")
        add("E/W", 3, raw(3), "Полушарие долготы")
        add("UTC time", 4, _format_utc(raw(4)), "Время UTC")
        add("Status", 5, status.get(raw(5), raw(5)), "Действительность координат")
        add("Mode", 6, raw(6), "Индикатор режима, если поддерживается")

    elif message == "VTG":
        speed_kn = _safe_float(raw(4))
        speed_kmh = _safe_float(raw(6))
        add("True track", 0, raw(0) + (" deg" if raw(0) != "-" else ""), "Истинный курс относительно земли")
        add("True marker", 1, raw(1), "T = true course")
        add("Magnetic track", 2, raw(2) + (" deg" if raw(2) != "-" else ""), "Магнитный курс, если доступен")
        add("Mag marker", 3, raw(3), "M = magnetic course")
        add("Speed knots", 4, "-" if speed_kn is None else f"{speed_kn:.3f} kn", "Скорость в узлах")
        add("Knots marker", 5, raw(5), "N = knots")
        add("Speed km/h", 6, "-" if speed_kmh is None else f"{speed_kmh:.3f} km/h", "Скорость в километрах в час")
        add("km/h marker", 7, raw(7), "K = km/h")
        add("Mode", 8, raw(8), "Индикатор режима, если поддерживается")

    elif message == "TXT":
        add("Messages total", 0, raw(0), "Количество частей текстового сообщения")
        add("Message number", 1, raw(1), "Номер текущей части")
        add("Message type", 2, raw(2), "Код типа текстового сообщения")
        add("Text", 3, raw(3), "Текст, переданный приемником")

    else:
        for index, value in enumerate(f):
            add(f"Field {index + 1}", index, value or "-", "Неизвестное или пока не описанное поле")

    return {
        "sentence_id": f"{sentence.talker}{sentence.message_type}",
        "summary": MESSAGE_SUMMARIES.get(
            sentence.message_type,
            "NMEA sentence / предложение NMEA",
        ),
        "checksum": "PASS" if sentence.checksum_ok else "FAIL",
        "rows": rows,
    }
