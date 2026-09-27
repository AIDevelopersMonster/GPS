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

modules/u-blox/NEO-6M/GY-GPS6MV2/

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

## Tools

Planned:

- `gps-cli` - automated command-line diagnostics
- `gps-gui` - graphical diagnostics and configuration
- shared diagnostic core used by both interfaces

## Video reports

- Git + GitHub from scratch using the GPS project: https://youtu.be/1EewXEMynV0

## Status

Initial project architecture.

LAB-01 will use the GY-GPS6MV2 board with u-blox NEO-6M as the first reference device.
