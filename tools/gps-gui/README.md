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

## v0.1 functions

- serial-port selection and refresh;
- baud selection;
- automatic baud/protocol probe;
- connect/disconnect;
- live NMEA/UBX detection;
- 2D/3D/fix state;
- satellites used/visible;
- HDOP;
- latitude/longitude;
- altitude and UTC;
- GGA update-rate estimate;
- raw serial monitor;
- raw binary capture;
- read-only u-blox `UBX-MON-VER` identification.

CLI and GUI use the same parser and diagnostic state model.
