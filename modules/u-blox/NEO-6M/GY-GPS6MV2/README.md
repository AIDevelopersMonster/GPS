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


## Memory / configuration architecture

The NEO-6M itself is a ROM-based receiver. Its normal runtime configuration is
held in volatile Current Configuration (RAM). Persistent configuration can be
stored in supported non-volatile devices and loaded back at startup.

For u-blox 6, `UBX-CFG-CFG` selects persistent devices with `deviceMask`:

- bit 0 — battery-backed RAM (BBR);
- bit 1 — Flash;
- bit 2 — external EEPROM;
- bit 4 — external SPI Flash.

The NEO-6 DDC/I2C interface explicitly supports an optional external serial
EEPROM for permanent receiver configuration. u-blox lists 32-kbit devices such
as ST `M24C32-R`, Microchip `24AA32A`, Catalyst `CAT24C32`, and Samsung
`S524AB0X91`. A 32-kbit EEPROM provides 4096 bytes of storage.

At startup, the receiver probes the expected EEPROM on the DDC bus. u-blox
documentation describes the device at 8-bit I2C address `0xA0` (7-bit address
`0x50`). If the EEPROM is detected, the receiver becomes DDC bus master for
that startup session. External masters must therefore not be attached casually
to the live DDC bus.

The photographed laboratory sample contains an 8-pin serial memory device
with the clearly readable top marking `24C32`. This confirms a 24C32-class
32-kbit (4096-byte) I2C serial EEPROM on this GY-GPS6MV2 board. The second
marking line is not sufficiently legible in the current photograph to assign a
manufacturer-specific part number, so the exact vendor remains **TBD**.

### EEPROM purpose

The external EEPROM is primarily configuration storage. It is not the NEO-6M
firmware store and is not a general NMEA logging memory.

Runtime `UBX-CFG-*` writes change the Current Configuration in RAM. A later
`UBX-CFG-CFG/save` operation can copy selected configuration groups into the
external EEPROM. `UBX-CFG-CFG/load` restores them.

Configuration groups include I/O ports, message configuration, INF messages,
navigation configuration, receiver-manager configuration, remote inventory,
and antenna configuration.

### EEPROM versus SPI Flash

Do not treat the onboard 24C32-class EEPROM as SPI Flash. u-blox 6 can also use
an optional external SPI Flash (minimum 1 Mbit according to the integration
manual) for receiver configuration and AssistNow Offline data. No SPI Flash is
yet confirmed on this laboratory GY-GPS6MV2 sample.

### Planned non-destructive persistence test

A safe EEPROM proof should avoid arbitrary memory writes:

1. read one harmless current configuration item;
2. save its configuration group to **EEPROM only**;
3. change the item in RAM only;
4. load the same group from EEPROM;
5. verify that the original value is restored;
6. report ACK/NAK and read-back result.

This proves the receiver can write and read persistent EEPROM through its own
u-blox storage mechanism while preserving the original configuration.

Raw 4-KiB EEPROM dumping is not exposed by the normal UBX UART protocol. That
would require physical access to the DDC/I2C bus or direct access to the EEPROM
device and must account for the NEO-6 receiver acting as DDC master.

### Primary references

- u-blox NEO-6 Data Sheet — external serial EEPROM on DDC for permanent configuration.
- u-blox LEA-6 / NEO-6 / MAX-6 Hardware Integration Manual — supported EEPROM parts,
  startup EEPROM probe, DDC master behavior, and optional SPI Flash.
- u-blox 6 Receiver Description / Protocol Specification — Current Configuration,
  Permanent Configuration, `UBX-CFG-CFG`, configuration groups, and device masks.
