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


## Registry management and reports

The SQLite database is the primary record:

```text
C:\Users\<USER>\.gpslab\gpslab.sqlite3
```

The GUI v0.6 includes a **Registry / Provisioning** manager with:

- physical database status and record count;
- module substring filter;
- result filter;
- table of stored inspections;
- record detail viewer including diagnostic JSON;
- summary counts;
- CSV export for Excel or further analysis;
- HTML report for the full registry or a selected module;
- SQLite backup using the SQLite online backup API;
- JSON export.

### CLI examples

Database status:

```powershell
py -m gpslab.registry_cli status
```

Summary:

```powershell
py -m gpslab.registry_cli summary
```

Find PASS records:

```powershell
py -m gpslab.registry_cli find --result PASS --limit 100
```

Find a module by partial number:

```powershell
py -m gpslab.registry_cli find --module 00001
```

Show one complete record, including its diagnostic payload:

```powershell
py -m gpslab.registry_cli show GPS6-2026-00001
```

Export all records to CSV:

```powershell
py -m gpslab.registry_cli export-csv .\gpslab.csv
```

Generate a complete HTML report:

```powershell
py -m gpslab.registry_cli report .\gpslab-report.html
```

Generate an HTML report for one module:

```powershell
py -m gpslab.registry_cli report .\GPS6-2026-00001.html --module-code GPS6-2026-00001
```

Create a consistent database backup:

```powershell
py -m gpslab.registry_cli backup .\backup\gpslab-20261001.sqlite3
```

Existing JSON export remains available:

```powershell
py -m gpslab.registry_cli export-json .\gpslab-export.json
```

### Data retention

The SQLite file is the source of truth. CSV, JSON and HTML files are exports and
may be recreated at any time. Back up the SQLite file itself regularly if the
registry becomes operationally important.
