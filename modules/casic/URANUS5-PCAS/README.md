# URANUS5 / PCAS receiver

This directory documents a GNSS receiver from an NEO-6M-lookalike module that does not behave like a genuine u-blox 6 receiver at protocol level.

## What was observed

Initial UART output was valid NMEA at 115200 8N1 and GNSS UTC was valid.

Classic u-blox requests were rejected with UBX ACK-NAK:

```text
CFG-PRT  -> NAK
MON-VER  -> NAK
CFG-RATE -> NAK
```

The PCAS firmware query:

```text
$PCAS06,0*1B
```

returned:

```text
$GPTXT,01,01,02,SW=URANUS5,V5.3.0.0*1D
```

Therefore the tested receiver identifies its firmware as **URANUS5 V5.3.0.0** and accepts the PCAS command family.

This is consistent with CASIC / Zhongkewei AT6558-family receivers, but the exact IC is not yet proven. Query the hardware model separately:

```text
$PCAS06,1*1A
```

## How to distinguish it from a genuine u-blox NEO-6M

1. Find the active UART baud rate from valid NMEA.
2. Send read-only UBX-MON-VER.
3. A genuine u-blox receiver should return MON-VER data.
4. If MON-VER is rejected, try `$PCAS06,0*1B\r\n`.
5. A `SW=URANUS5,...` GPTXT reply identifies the PCAS/URANUS5 firmware family.

Do not identify a module only from the PCB label or metal-can marking.

## Useful PCAS product queries

| Purpose | Command |
|---|---|
| Firmware version | `$PCAS06,0*1B` |
| Hardware model / serial | `$PCAS06,1*1A` |
| Working mode | `$PCAS06,2*19` |
| Product/customer number | `$PCAS06,3*18` |
| Upgrade-code information | `$PCAS06,5*1E` |

## UART baud rate

PCAS01 configures the NMEA UART baud rate.

| Baud | Command |
|---:|---|
| 4800 | `$PCAS01,0*1C` |
| 9600 | `$PCAS01,1*1D` |
| 19200 | `$PCAS01,2*1E` |
| 38400 | `$PCAS01,3*1F` |
| 57600 | `$PCAS01,4*18` |
| 115200 | `$PCAS01,5*19` |

The tested module was changed from 115200 to 9600 with:

```text
$PCAS01,1*1D
```

After sending it, reconnect the host UART at 9600 and verify valid NMEA and GNSS time.

## Save configuration

The PCAS save command is:

```text
$PCAS00*01
```

Recommended procedure:

```text
change setting
-> reconnect using the new setting
-> verify NMEA / time
-> send $PCAS00*01
-> remove power
-> power on
-> verify that the setting survived
```

The power-cycle check is the final proof that the specific module has usable non-volatile configuration storage.

## Other useful commands

Restart modes:

| Action | Command |
|---|---|
| Hot start | `$PCAS10,0*1C` |
| Warm start | `$PCAS10,1*1D` |
| Cold start | `$PCAS10,2*1E` |
| Factory start | `$PCAS10,3*1F` |

Factory start resets configuration and must not be used as an identification probe.

Some common constellation commands:

| Mode | Command |
|---|---|
| GPS only | `$PCAS04,1*18` |
| BeiDou only | `$PCAS04,2*1B` |
| GPS + BeiDou | `$PCAS04,3*1A` |
| GPS + GLONASS | `$PCAS04,5*1C` |
| GPS + BeiDou + GLONASS | `$PCAS04,7*1E` |

Implementation can vary by firmware, so verify the result from actual NMEA output.

## PCAS checksum

PCAS text commands use an NMEA-style XOR checksum of the characters between `$` and `*`, followed by CR/LF.

## Binary CASIC protocol

CASIC also defines a binary protocol distinct from u-blox UBX.

```text
u-blox UBX sync : B5 62
CASIC sync      : BA CE
```

Partial UBX-like behaviour is not proof of a u-blox receiver.

## Video

Laboratory video showing identification and UART speed change:

https://youtu.be/LIAIyjDMms8

## References

Manufacturer-hosted CASIC protocol specification:

https://icofchina.com/d/file/xiazai/2020-09-22/20f1b42b3a11ac52089caf3603b43fb5.pdf

English AT6558 protocol mirror:

https://wiki.wirenboard.com/wiki/images/5/53/AT6558-protocol-en.pdf

Quectel L76K/L26K protocol reference using PCAS commands:

https://forums.quectel.com/uploads/short-url/kmb3zNuV2SldThkOOJoNg9th40S.pdf

Espruino technical notes with real URANUS5 V5.3.0.0 / AT6558R examples:

https://github.com/espruino/EspruinoDocs/blob/master/info/Bangle.js2%20Technical.md

## Non-claims

Current evidence does not yet prove the exact silicon part number or manufacturer of the complete breakout board. Those require direct identification of the specific sample.
