from __future__ import annotations

from datetime import datetime, timezone


def parse_nmea_utc(date_text: str | None, time_text: str | None) -> datetime | None:
    """Convert RMC ddmmyy + NMEA hhmmss.sss to an aware UTC datetime."""
    if not date_text or not time_text:
        return None

    date_text = date_text.strip()
    time_text = time_text.strip()
    if len(date_text) != 6 or len(time_text) < 6:
        return None

    try:
        day = int(date_text[0:2])
        month = int(date_text[2:4])
        year2 = int(date_text[4:6])

        hour = int(time_text[0:2])
        minute = int(time_text[2:4])
        seconds_float = float(time_text[4:])
        second = int(seconds_float)
        microsecond = int(round((seconds_float - second) * 1_000_000))

        if microsecond >= 1_000_000:
            second += 1
            microsecond -= 1_000_000

        year = 2000 + year2 if year2 < 80 else 1900 + year2

        return datetime(
            year,
            month,
            day,
            hour,
            minute,
            second,
            microsecond,
            tzinfo=timezone.utc,
        )
    except (ValueError, TypeError):
        return None


def utc_delta_seconds(
    date_text: str | None,
    time_text: str | None,
    reference: datetime | None = None,
) -> float | None:
    gnss = parse_nmea_utc(date_text, time_text)
    if gnss is None:
        return None

    reference = reference or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    return (gnss - reference.astimezone(timezone.utc)).total_seconds()


def time_sync_status(
    *,
    date_text: str | None,
    time_text: str | None,
    satellites_visible: int | None,
    tolerance_seconds: float = 5.0,
    reference: datetime | None = None,
) -> tuple[bool, float | None]:
    """Practical GNSS-time confirmation against the host UTC clock."""
    delta = utc_delta_seconds(date_text, time_text, reference)
    if delta is None:
        return False, None

    if not satellites_visible or satellites_visible <= 0:
        return False, delta

    return abs(delta) <= tolerance_seconds, delta
