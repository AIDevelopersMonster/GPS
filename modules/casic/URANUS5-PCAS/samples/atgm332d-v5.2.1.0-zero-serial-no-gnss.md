# Laboratory sample — ATGM332D / URANUS5 V5.2.1.0 / zero serial / no GNSS reception

This record documents a second NEO-6M-lookalike receiver that was digitally
responsive but did not acquire usable GNSS data during the laboratory check.

## Protocol identity

Observed PCAS replies:

```text
$GPTXT,01,01,02,MA=CASIC*27
$GPTXT,01,01,02,HW=ATGM332D,0000000000000*1A
$GPTXT,01,01,02,IC=AT6558-5N-31-0C510800,J9M10CL-A3-001025*22
$GPTXT,01,01,02,SW=URANUS5,V5.2.1.0*1D
$GPTXT,01,01,02,TB=2019-08-12,10:01:36*4E
$GPTXT,01,01,02,MO=GB*77
$GPTXT,01,01,02,BS=SOC_BootLoader,V6.2.0.2*34
$GPTXT,01,01,02,FI=00EF4014*7D
```

Observed identity:

- manufacturer/firmware family: `CASIC / URANUS5`;
- reported hardware: `ATGM332D`;
- reported IC: `AT6558-5N-31-0C510800`;
- chip trace string: `J9M10CL-A3-001025`;
- working mode: `GB` (GPS + BeiDou);
- reported hardware serial field: `0000000000000`.

The all-zero hardware serial is treated as **not a usable factory identifier**.

## Navigation failure

The receiver continuously produced syntactically valid NMEA, but the useful
navigation fields remained empty:

```text
$GNRMC,,V,,,,,,,,,,M*4E
$GNVTG,,,,,,,,,M*2D
$GNGGA,,,,,,0,00,25.5,,,,,,*64
```

Laboratory result:

- UART / NMEA transport: PASS;
- PCAS command path: PASS;
- firmware/hardware identification: PASS;
- GNSS UTC: FAIL;
- satellites used: 0;
- navigation fix: FAIL.

A forced GPS+BeiDou mode and cold restart were also tested:

```text
$PCAS04,3*1A
$PCAS10,2*1E
```

After restart the receiver booted normally and returned its full identification
banner, but GNSS reception still did not become usable.

## Antenna / RF observation

After enabling the diagnostic NMEA/TXT output, the receiver repeatedly reported:

```text
$GPTXT,01,01,01,ANTENNA OPEN*25
```

This message alone is not proof of a physical open circuit because passive
antenna configurations may also be reported as `ANTENNA OPEN` on this family.
However, in this sample it coincided with:

- no GNSS UTC;
- zero satellites used;
- invalid RMC;
- no navigation fix.

The most likely problem area is therefore the antenna/RF receive path, but the
sample was **not disassembled or repaired** and the exact hardware fault was not
investigated further.

## Practical warning

NEO-6M-lookalike boards may contain a fully responsive CASIC/ATGM332D digital
receiver while the GNSS receive path is unusable. Valid UART traffic, valid PCAS
replies, and successful identification are therefore **not sufficient proof of a
working GNSS receiver**.

For GPS Lab, acquisition of GNSS UTC remains a separate acceptance criterion.
