# NMEA + UBX protocol reference

Interactive standalone HTML references used by GPS Lab.

## GitHub Pages

- [GPS Lab documentation home](https://aidevelopersmonster.github.io/GPS/)
- [NMEA + UBX reference — Russian](https://aidevelopersmonster.github.io/GPS/protocols/nmea-ubx-reference.html)
- [NMEA + UBX reference — English](https://aidevelopersmonster.github.io/GPS/protocols/nmea-ubx-reference-en.html)

## Local use

The same files are fully standalone and can be opened without a web server:

- [Russian HTML](nmea-ubx-reference.html)
- [English HTML](nmea-ubx-reference-en.html)

From the repository root in PowerShell:

```powershell
Start-Process .\docs\index.html
Start-Process .\docs\protocols\nmea-ubx-reference.html
Start-Process .\docs\protocols\nmea-ubx-reference-en.html
```

The Pages deployment publishes the existing `docs/` files; it does not replace or transform the local copies.
