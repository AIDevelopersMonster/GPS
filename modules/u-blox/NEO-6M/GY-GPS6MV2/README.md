# GY-GPS6MV2 / u-blox NEO-6M

First reference hardware for the GPS project.

## Sample identification

Observed markings on the photographed sample:

- PCB: `GY-GPS6MV2`
- GNSS module: `NEO-6M-0-001`
- manufacturer family: u-blox NEO-6

External connections visible on the board:

- VCC
- RX
- TX
- GND
- u.FL / IPEX antenna connector

The sample includes an external ceramic patch antenna.

## Important rule

Board-level characteristics must not automatically be treated as NEO-6M chip characteristics.

For example:

- board supply voltage;
- UART voltage levels;
- antenna bias;
- EEPROM implementation;
- backup supply implementation

must be documented or measured for the actual board.

## LAB-01

Initial tests will cover:

1. visual identification;
2. power rails;
3. UART detection;
4. factory baud rate;
5. raw NMEA capture;
6. UBX detection;
7. satellite visibility;
8. navigation fix;
9. antenna behaviour;
10. configuration persistence.

## Current status

Hardware sample available.

Electrical measurements not yet recorded.

UART capture not yet recorded.
