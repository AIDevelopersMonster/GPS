# GPS Lab certification and module attestation

This document defines the open certification mechanism used to bind a GPS/GNSS
module to a diagnostic report without requiring a printed external serial label.

## Goals

The mechanism must prove, as far as the receiver capabilities allow, that:

1. a specific logical module identity was provisioned;
2. the module passed a named GPS Lab diagnostic profile;
3. the date/time of the test is recorded;
4. a local receipt is retained;
5. the receipt can be independently verified using public code and a public key;
6. the receiver stores a compact matching attestation record in Remote Inventory.

## Important limitation

u-blox 6 / NEO-6M does not expose a documented factory-unique silicon identifier
through the interfaces tested in this project. Therefore the GPS Lab identity is
a provisioned logical identity, not an immutable hardware root of trust.

A copied EEPROM/RINV image could clone that logical identity onto another receiver.
The Ed25519 signature still proves that the receipt was issued by the holder of the
GPS Lab station private key, but without an immutable device-unique secret it cannot
cryptographically prove that a cloned receiver is the original physical silicon.

This limitation is explicit and must be preserved in every certification workflow.

## Two-part evidence model

### Part A: record stored inside the receiver

Remote Inventory stores exactly 30 bytes:

```text
Offset  Size  Meaning
0       4     Magic "GLP1"
4       8     GPS Lab Module ID (64 random bits)
12      4     Test timestamp, Unix UTC, big-endian
16      4     Station public-key ID = first 4 bytes SHA-256(public key)
20      10    First 10 bytes SHA-256(canonical signed receipt core)
```

The human-readable module ID is rendered as:

```text
GPS6-XXXX-XXXX-XXXX-XXXX
```

The RINV record says, in compact form: this logical module identity passed a
GPS Lab test at this time and is linked to a receipt produced by this station key.

### Part B: signed receipt stored by the test station

The local JSON receipt contains:

- module ID;
- test date/time in UTC;
- station name;
- station public-key fingerprint;
- receiver family, SW and HW versions;
- test profile name;
- every PASS/FAIL check;
- measured engineering values;
- RINV contents before provisioning;
- RINV bytes written;
- EEPROM save evidence;
- read-back evidence;
- power-cycle persistence evidence;
- Ed25519 signature;
- receipt ID.

The receipt is signed with Ed25519. The private key remains local and encrypted.
The public key may be published with the open-source verifier.

## Why the receipt hash in RINV is not the final receipt hash

The receiver record must be known before the final write evidence exists. To avoid
a circular dependency, RINV stores a truncated SHA-256 of the immutable receipt
**core**: identity, date, station, profile, receiver information, checks and
measurements.

The final receipt additionally contains the actual write/read-back/power-cycle
evidence and is then signed.

## Required certification sequence

```text
READ CFG-RINV
  -> require EMPTY / FACTORY DEFAULT for first provisioning
RUN diagnostic profile
  -> all mandatory checks must PASS
CREATE receipt core
CREATE random Module ID
CREATE 30-byte GLP1 RINV record
WRITE CFG-RINV to current configuration
READ CFG-RINV back
  -> exact byte-for-byte match required
SAVE rinvConf to EEPROM only using UBX-CFG-CFG
POWER CYCLE receiver
READ CFG-RINV again
  -> exact byte-for-byte persistence match required
CREATE final receipt with all write evidence
SIGN final receipt with station Ed25519 private key
STORE receipt locally
VERIFY receipt with public key
```

No PASS receipt should be issued before the power-cycle read-back succeeds.

## Station key setup

Install the package, then:

```powershell
gps-cert init-station --station-name "GPS Lab"
```

The default directory is:

```text
~/.gpslab/certification/
```

It contains:

```text
station_private.pem   encrypted private signing key
station_public.pem    public verification key
station.json          station metadata and public-key fingerprint
receipts/             locally retained signed receipts
```

The private key must never be committed to GitHub.

## Independent verification

A receipt can be verified with only the open-source tool and public key:

```powershell
gps-cert verify-receipt receipt.json --public-key station_public.pem
```

A 30-byte RINV record can be decoded independently:

```powershell
gps-cert decode-rinv "47 4C 50 31 ..."
```

The verifier checks:

- Ed25519 signature;
- receipt ID;
- public-key fingerprint;
- Module ID equality between receipt and RINV;
- station key ID equality;
- receipt-core hash prefix equality;
- PASS result.

## Open-source trust model

The verifier is intentionally public. Trust does not depend on secret software.
Trust depends on possession of the station private key and publication of the
corresponding public key/fingerprint.

Anyone can inspect the encoding, recompute all hashes and verify the signature.
