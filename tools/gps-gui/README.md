# GPS-GUI

Graphical interface for the shared `gpslab` diagnostic core.

The GUI uses Python's standard Tk interface and `pyserial`.

## Install

From the repository root:

```powershell
py -m pip install -e .
```

## Start

```powershell
gps-gui
```

## v0.4 functions

- serial-port selection and refresh;
- baud selection and automatic baud/protocol probe;
- connect/disconnect;
- live NMEA/UBX detection;
- receiver state, 2D/3D fix, satellites, HDOP and position;
- GNSS UTC compared with host UTC, with `TIME PASS` status;
- raw serial monitor and binary capture;
- receiver identity through read-only UBX polls;
- `MON-VER` software/hardware/protocol information;
- `CFG-USB` serial string when implemented by the receiver;
- `SEC-UNIQID` unique ID when implemented by the receiver generation;
- UBX terminal with TX/RX log;
- Engineering tab with read-only MON-HW, MON-IO, MON-RXBUF and MON-TXBUF diagnostics;
- RF/hardware view for noise, AGC, antenna state and receiver jamming indicators;
- I/O error counters and RX/TX buffer load views.

## Identity

The **Identify** button sends three read-only polls:

```text
UBX-MON-VER
UBX-CFG-USB
UBX-SEC-UNIQID
```

Older u-blox generations may not implement every poll. In particular, a NEO-6M can return useful `MON-VER` information while leaving serial or unique-ID fields unavailable. A blank field therefore means "not returned / not supported", not receiver failure.

## UBX terminal

The terminal is intentionally protocol-aware. It does **not** accept modem-style AT commands because u-blox NEO-6M service communication uses UBX, not an AT command set.

Paste a complete UBX packet as hexadecimal bytes and press **Send**. The GUI transmits only packets whose sync, length and checksum are valid.

Example read-only MON-VER poll:

```text
B5 62 0A 04 00 00 0E 34
```

CLI and GUI use the same parser and diagnostic state model.


## Engineering diagnostics

The Engineering tab sends read-only monitor polls only:

```text
UBX-MON-HW
UBX-MON-IO
UBX-MON-RXBUF
UBX-MON-TXBUF
```

`MON-HW` exposes receiver hardware/RF diagnostics such as noise level,
AGC count, antenna status, and the receiver's jamming indicators. These
values are diagnostic observations from the receiver; by themselves they
do not identify an interference source and do not prove spoofing.

`MON-IO` shows per-port RX/TX byte counters and serial errors.
`MON-RXBUF` and `MON-TXBUF` expose pending bytes and buffer usage.

Configuration writes are intentionally not enabled in this first
Engineering step. The next write-capable layer should follow:
READ current -> show OLD/NEW -> write RAM -> ACK -> read back -> optional SAVE.
