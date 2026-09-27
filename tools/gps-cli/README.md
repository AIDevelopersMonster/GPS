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

## v0.1 safety policy

GPS-CLI v0.1 does not write receiver configuration.

The only active protocol request is the u-blox `UBX-MON-VER` poll used to read receiver/version information.
