# Laboratory sample — ATGM332D / URANUS5 V5.2.1.0

This record captures a protocol-level identification of an NEO-6M-lookalike
receiver tested with GPS Lab PCAS Terminal.

## Observed UART / navigation state

- active UART: 115200 8N1 at the time of identification;
- valid NMEA output;
- GNSS UTC received;
- no navigation fix at the captured moment;
- repeated antenna diagnostic: `ANTENNA OPEN`.

## Firmware identity

Command:

```text
$PCAS06,0*1B
```

Observed reply:

```text
$GPTXT,01,01,02,SW=URANUS5,V5.2.1.0*1D
```

Protocol-level firmware identity:

```text
URANUS5 V5.2.1.0
```

## Hardware identity

Command:

```text
$PCAS06,1*1A
```

Observed reply:

```text
$GPTXT,01,01,02,HW=ATGM332D,0009101407754*16
```

The receiver therefore reports:

- hardware family/model: `ATGM332D`;
- reported module/receiver serial-like value: `0009101407754`.

This is stronger evidence than a PCB or shield marking because it is returned
by the receiver firmware itself.

It still does not prove the exact silicon die or ATGM332D subvariant without
additional evidence.

## Antenna diagnostic

Observed:

```text
$GPTXT,01,01,01,ANTENNA OPEN*25
```

ATGM332D documentation describes GPTXT antenna states including:

- `ANTENNA SHORT`;
- `ANTENNA OPEN`;
- `ANTENNA OK`.

The manual also notes that passive-antenna use can report `ANTENNA OPEN`, so
this sentence must not automatically be treated as proof of a broken antenna
connection.

## Identification sequence used in GPS Lab

```text
Connect at current UART baud
-> PCAS Terminal
-> Firmware
-> $PCAS06,0*1B
-> SW=URANUS5,V5.2.1.0

-> Hardware
-> $PCAS06,1*1A
-> HW=ATGM332D,0009101407754
```

## Video

UART configuration and PCAS investigation:

https://youtu.be/LIAIyjDMms8
