# Diagnostic tools

The GPS project uses one shared diagnostic core for both command-line and graphical interfaces.

```text
Serial / transport
        |
        v
NMEA + UBX parsers
        |
        v
Shared diagnostic state
       / \
      /   \
 GPS-CLI  GPS-GUI
```

Current implementation: `gpslab` v0.1.

See:

- `tools/gps-cli/README.md`
- `tools/gps-gui/README.md`

The v0.1 toolchain is intentionally conservative: it reads receiver output and supports a read-only u-blox MON-VER identity poll, but does not change receiver configuration.
