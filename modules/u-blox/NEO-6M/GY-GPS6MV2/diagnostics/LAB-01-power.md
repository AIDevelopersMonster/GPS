# LAB-01 — Power and Electrical Baseline

Sample: `GPS-NEO6M-001`

Board: `GY-GPS6MV2`

Receiver marking: `NEO-6M-0-001`

## Purpose

Establish the basic electrical behaviour of the physical sample before connecting UART or a microcontroller.

## Instruments

- regulated DC supply or known USB power source;
- digital multimeter;
- optional USB current meter.

## Safety rule

Do not probe the RF connector center pin unless the probe can be placed without shorting the center conductor to the outer shield.

Do not connect UART until board power and logic levels have been checked.

---

## Test A — Unpowered resistance checks

Power: OFF

| Measurement | Result | Status |
|---|---:|---|
| VCC to GND resistance | TBD | NOT TESTED |
| RX to GND resistance | TBD | NOT TESTED |
| TX to GND resistance | TBD | NOT TESTED |

Notes:

TBD

---

## Test B — Board input

Applied supply:

`TBD V`

| Measurement | Result | Status |
|---|---:|---|
| Voltage at VCC-GND | TBD V | NOT TESTED |
| Input current | TBD mA | NOT TESTED |

Notes:

TBD

---

## Test C — Internal power rail

| Measurement | Result | Status |
|---|---:|---|
| GNSS module supply rail | TBD V | NOT TESTED |
| Regulator input | TBD V | NOT TESTED |
| Regulator output | TBD V | NOT TESTED |

Exact regulator pins must be identified before measurement.

---

## Test D — UART idle levels

UART not externally connected.

| Measurement | Result | Status |
|---|---:|---|
| Board TX to GND | TBD V | NOT TESTED |
| Board RX to GND | TBD V | NOT TESTED |

The TX idle level is especially useful for determining the receiver-side logic voltage.

---

## Test E — RF connector DC bias

Only perform if the RF connector can be probed safely.

| Measurement | Result | Status |
|---|---:|---|
| RF center to GND | TBD V | NOT TESTED |

Possible interpretations will be documented only after measurement.

---

## Test F — Power cycle

1. Power board.
2. Observe LEDs.
3. Remove power.
4. Reapply power.

| Observation | Result |
|---|---|
| Power LED | TBD |
| Other LED activity | TBD |
| Behaviour after power cycle | TBD |

---

## Completion criteria

LAB-01 electrical baseline is complete when we know:

- actual applied board voltage;
- board current consumption;
- internal GNSS supply voltage;
- UART TX idle voltage;
- whether RF DC bias is present;
- visible LED behaviour.

No conclusions about UART protocol or GPS fix belong to this test.
