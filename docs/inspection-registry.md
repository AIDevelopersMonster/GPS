# GPS Lab inspection registry

The project uses a simple technological identification scheme. It is not a
certificate, signature, legal attestation, or anti-cloning mechanism.

## Receiver marker

After a module passes the selected laboratory profile, CFG-RINV may contain a
human-readable marker such as:

```text
GPS6-2026-00001 20261001 OK
```

Meaning:

- `GPS6` - receiver family used by this laboratory line;
- `2026` - year in which the sequential laboratory number was issued;
- `00001` - sequential inspection/module number;
- `20261001` - inspection date in UTC;
- `OK` - the module passed the selected laboratory profile at that time.

The marker is intentionally open and copyable. It is only an internal
technological reference linking the physical module to our local inspection log.

## Local database

The primary store is SQLite:

```text
~/.gpslab/gpslab.sqlite3
```

SQLite was selected instead of a single JSON file because it safely handles many
thousands of records, sequential numbering, indexing, and later queries without
loading or rewriting the entire history.

A record stores:

- internal numeric row ID;
- module code;
- UTC test date/time;
- board;
- receiver identity;
- SW/HW version;
- result;
- test profile;
- RINV value before and after provisioning;
- complete diagnostic snapshot as JSON inside SQLite.

For portability the full database can be exported to JSON.

## CLI

List recent records:

```powershell
gps-registry list --limit 20
```

Export the complete registry:

```powershell
gps-registry export-json .\gpslab-export.json
```

## Planned provisioning flow

```text
READ CFG-RINV
  -> if EMPTY, allow first registration
RUN selected diagnostic profile
  -> collect diagnostic snapshot
ALLOCATE next module code in SQLite
  -> GPS6-YYYY-NNNNN
BUILD RINV text
  -> GPS6-YYYY-NNNNN YYYYMMDD OK
WRITE CFG-RINV
READ BACK
SAVE rinvConf to EEPROM
POWER CYCLE
READ BACK AGAIN
UPDATE SQLite record with final RINV/persistence result
```

No cryptography is involved. The purpose is traceability for our own engineering
workflow.
