# GPS

Open hardware/software laboratory for GPS and GNSS modules.

The project collects:

- module identification and hardware documentation;
- pinouts, power and signal-level measurements;
- NMEA, UBX and other protocol documentation;
- reproducible diagnostic procedures;
- known problems and tested solutions;
- raw captures and experimental evidence;
- firmware examples for Arduino and ESP32;
- common diagnostic engine;
- GPS-CLI command-line tools;
- GPS-GUI diagnostic interface.

## First reference module

u-blox NEO-6M / GY-GPS6MV2

Path:

`modules/u-blox/NEO-6M/GY-GPS6MV2/`

## Project principle

Do not treat "no coordinates" as "GPS is broken".

Diagnostics should distinguish:

1. Power
2. UART communication
3. Valid protocol data
4. Receiver identification
5. Satellite visibility
6. 2D/3D fix
7. Position/time validity
8. Configuration persistence
9. Antenna/RF problems

## GPS-CLI and GPS-GUI

The first working diagnostic toolchain is implemented as the shared Python package `gpslab`.

Install from the repository root:

```powershell
py -m pip install -e .
```

List serial ports:

```powershell
gps-cli ports
```

Auto-probe a receiver:

```powershell
gps-cli probe COM7
```

Monitor live navigation status:

```powershell
gps-cli monitor COM7 --baud 9600
```

Launch the graphical console:

```powershell
gps-gui
```

Both interfaces use the same NMEA/UBX parsers and diagnostic state model.

Version 0.1 is intentionally conservative: it reads receiver output and can send the read-only u-blox `UBX-MON-VER` identity poll, but it does not change receiver configuration.

See:

- `tools/README.md`
- `tools/gps-cli/README.md`
- `tools/gps-gui/README.md`

## Protocol reference

Standalone searchable HTML reference for NMEA and UBX:

`docs/protocols/nmea-ubx-reference.html`

Covers NMEA framing/checksum, GGA/RMC/GSA/GSV/GLL/VTG/ZDA/TXT, UBX framing/checksum,
message classes, GPS Lab UBX polls, ACK/NAK, CFG-RINV/NVM and diagnostic workflow.

## Additional receiver families

A tested NEO-6M-lookalike receiver identified itself as `URANUS5 V5.3.0.0` and accepts the PCAS command family rather than the classic u-blox configuration path.

Documentation:

`modules/casic/URANUS5-PCAS/README.md`

It includes identification clues, PCAS commands, UART baud-rate change (including 115200 -> 9600), non-volatile save, restart modes, constellation commands, protocol references, and explicit non-claims about the exact silicon.

## Video reports

- Git + GitHub from scratch using the GPS project: https://youtu.be/1EewXEMynV0
- URANUS5 / PCAS clone investigation and UART speed change: https://youtu.be/LIAIyjDMms8

## Status

- Repository architecture: active
- Shared diagnostic core: v0.1
- GPS-CLI: v0.1
- GPS-GUI: v0.1
- First hardware laboratory: GY-GPS6MV2 / u-blox NEO-6M
