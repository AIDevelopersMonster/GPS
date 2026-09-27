from __future__ import annotations

import time
from dataclasses import dataclass

try:
    import serial
    from serial.tools import list_ports
except ImportError as exc:
    serial = None
    list_ports = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from .diagnostics import GPSDiagnostics
from .models import GPSState
from .ubx import MON_VER_POLL


DEFAULT_BAUD_RATES = [9600, 4800, 19200, 38400, 57600, 115200]


@dataclass
class PortInfo:
    device: str
    description: str
    hwid: str


def require_pyserial() -> None:
    if serial is None:
        raise RuntimeError(
            "pyserial is required. Install with: py -m pip install -e ."
        ) from _IMPORT_ERROR


def list_serial_ports() -> list[PortInfo]:
    require_pyserial()
    return [
        PortInfo(
            device=item.device,
            description=item.description or "",
            hwid=item.hwid or "",
        )
        for item in list_ports.comports()
    ]


def open_serial(port: str, baud: int, timeout: float = 0.1):
    require_pyserial()
    return serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=timeout,
        write_timeout=1.0,
    )


def passive_sample(
    port: str,
    baud: int,
    seconds: float = 1.5,
) -> GPSDiagnostics:
    diag = GPSDiagnostics(port=port, baud=baud)

    with open_serial(port, baud) as ser:
        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            waiting = getattr(ser, "in_waiting", 0)
            chunk = ser.read(waiting or 256)
            if chunk:
                diag.feed(chunk)

    return diag


def identify_ubx(
    port: str,
    baud: int,
    seconds: float = 1.0,
    diagnostics: GPSDiagnostics | None = None,
) -> GPSDiagnostics:
    diag = diagnostics or GPSDiagnostics(port=port, baud=baud)

    with open_serial(port, baud) as ser:
        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        ser.write(MON_VER_POLL)
        ser.flush()

        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            waiting = getattr(ser, "in_waiting", 0)
            chunk = ser.read(waiting or 256)
            if chunk:
                diag.feed(chunk)
                if diag.state.ubx_sw_version or diag.state.ubx_hw_version:
                    break

    return diag


def score_state(state: GPSState) -> int:
    score = 0
    score += state.nmea_valid * 100
    score += state.ubx_frames * 100
    score += min(state.bytes_received, 999)
    score -= state.nmea_invalid * 2
    return score


def probe_port(
    port: str,
    baud_rates: list[int] | None = None,
    seconds_per_baud: float = 1.5,
    identify: bool = True,
) -> GPSDiagnostics:
    baud_rates = baud_rates or DEFAULT_BAUD_RATES
    best: GPSDiagnostics | None = None
    best_score = -1

    for baud in baud_rates:
        try:
            diag = passive_sample(port, baud, seconds_per_baud)
        except Exception:
            continue

        current_score = score_state(diag.state)
        if current_score > best_score:
            best = diag
            best_score = current_score

        if diag.state.nmea_valid > 0 or diag.state.ubx_frames > 0:
            best = diag
            break

    if best is None:
        best = GPSDiagnostics(port=port)

    if identify and best.state.baud and best.state.has_protocol:
        try:
            best = identify_ubx(
                port=port,
                baud=best.state.baud,
                diagnostics=best,
            )
        except Exception:
            pass

    return best
