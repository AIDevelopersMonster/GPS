# GPS-CLI

Command-line diagnostic interface for the shared `gpslab` core.

## Install

From the repository root:

```powershell
py -m pip install -e .
```

## First commands

List ports:

```powershell
gps-cli ports
```

Auto-probe a receiver:

```powershell
gps-cli probe COM7
```

Probe only the expected factory baud:

```powershell
gps-cli probe COM7 --baud 9600
```

Live status:

```powershell
gps-cli monitor COM7 --baud 9600
```

Raw NMEA/UBX stream:

```powershell
gps-cli monitor COM7 --baud 9600 --raw
```

Read-only u-blox identity poll:

```powershell
gps-cli identify COM7 --baud 9600
```

Save a 60-second raw capture:

```powershell
gps-cli capture COM7 --baud 9600 --seconds 60 --output neo6m-001.bin
```

## Grouped output

Use `-g` / `--group` to select only the information needed in the terminal.

Available groups:

- `serial` - port, baud and byte counter;
- `protocol` - NMEA/UBX status and message counters;
- `receiver` - receiver identity and UBX version;
- `sat` - fix, satellites and HDOP;
- `nav` - latitude, longitude, altitude and speed;
- `time` - UTC and GGA update rate;
- `status` - diagnostic conclusion;
- `all` - all groups.

A single group:

```powershell
gps-cli probe COM4 --baud 9600 --no-identify -g protocol
```

Several groups:

```powershell
gps-cli probe COM4 --baud 9600 --no-identify -g serial -g protocol -g sat
```

Navigation only:

```powershell
gps-cli monitor COM4 --baud 9600 -g nav
```

Satellites plus navigation plus time:

```powershell
gps-cli monitor COM4 --baud 9600 -g sat -g nav -g time
```

Full grouped report:

```powershell
gps-cli probe COM4 --baud 9600 --no-identify -g all
```

Without `-g`, `probe`, `identify` and `capture` show all groups.
Without `-g`, `monitor` shows the useful live set: `sat + nav + time`.

## v0.1 safety policy

GPS-CLI v0.1 does not write receiver configuration.

The only active protocol request is the u-blox `UBX-MON-VER` poll used to read receiver/version information.
