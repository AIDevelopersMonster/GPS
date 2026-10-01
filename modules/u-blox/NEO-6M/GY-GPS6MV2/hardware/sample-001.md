# Sample 001 — GY-GPS6MV2 / NEO-6M

## Sample ID

`GPS-NEO6M-001`

## Evidence

Initial evidence set: photographs of the physical module and supplied antenna.

## Visual identification

### PCB marking

`GY-GPS6MV2`

### GNSS module marking

`NEO-6M-0-001`

Important: this marking identifies what the package claims to be.  
Authenticity and protocol-level identity have not yet been verified.

### External header

Visible board labels:

| Pin label | Visual status | Electrical status |
|---|---|---|
| VCC | confirmed | NOT TESTED |
| RX | confirmed | NOT TESTED |
| TX | confirmed | NOT TESTED |
| GND | confirmed | NOT TESTED |

### RF connection

The board has a miniature coaxial RF connector for an external antenna.

The sample was supplied with a ceramic patch antenna and coaxial cable.

Exact connector family and antenna electrical characteristics are not yet verified.

---

## Electrical characteristics

| Parameter | Result |
|---|---|
| Board input voltage | NOT TESTED |
| GNSS module supply voltage | NOT TESTED |
| UART TX idle voltage | NOT TESTED |
| UART logic level | NOT TESTED |
| Current consumption | NOT TESTED |
| Antenna bias voltage | NOT TESTED |
| Backup-domain voltage | NOT TESTED |

---

## Communication

| Parameter | Result |
|---|---|
| UART active | NOT TESTED |
| Factory baud rate | NOT TESTED |
| NMEA detected | NOT TESTED |
| UBX detected | NOT TESTED |
| Receiver identity via protocol | NOT TESTED |

---

## Navigation

| Parameter | Result |
|---|---|
| Satellites visible | NOT TESTED |
| 2D fix | NOT TESTED |
| 3D fix | NOT TESTED |
| UTC valid | NOT TESTED |
| Coordinates valid | NOT TESTED |
| TTFF cold start | NOT TESTED |

---

## Configuration persistence

| Test | Result |
|---|---|
| Settings survive reset | NOT TESTED |
| Settings survive power cycle | NOT TESTED |
| Backup retention | NOT TESTED |

---

## Open questions

1. Is the receiver electrically and protocol-compatible with a genuine u-blox NEO-6M?
2. What input voltage range does this specific GY-GPS6MV2 board accept?
3. What UART voltage levels are actually present?
4. What is the factory UART baud rate?
5. Does the receiver output NMEA, UBX, or both?
6. Is DC antenna bias present on the RF connector?
7. Is configuration persistence implemented on this board?
8. Does the backup domain retain time/almanac data after power removal?

---

## Laboratory rule

No specification from a generic GY-GPS6MV2 listing or NEO-6M datasheet is treated as a measured property of Sample 001 until it is verified.

Status terms:

- `CONFIRMED` — directly observed or measured;
- `NOT TESTED` — experiment not yet performed;
- `HYPOTHESIS` — plausible but unverified;
- `FAIL` — reproducibly failed;
- `PASS` — reproducibly passed.
