# GPS Project Architecture

## Goal

Build a reproducible GPS/GNSS module laboratory rather than a collection of isolated examples.

The project separates hardware access, protocols, diagnostics and user interfaces.

## Layers

Serial / transport layer

    ↓

Protocol layer

- NMEA
- UBX
- vendor-specific protocols

    ↓

Diagnostic core

    ↓

User interfaces

- CLI
- GUI
- firmware integrations

## Design rule

CLI and GUI must use the same diagnostic logic.

Hardware-specific knowledge belongs under `modules/`.

General diagnostic logic belongs under `tools/` and shared code that will be introduced later.

## Diagnostic state model

A receiver may pass some stages and fail later ones:

- no power
- no UART
- UART data detected
- valid protocol detected
- receiver identified
- satellites visible
- 2D fix
- 3D fix
- valid navigation solution

This distinction is important because lack of a position fix does not by itself mean that the receiver is defective.

## Evidence policy

Measurements and captures from real hardware should be preserved where practical.

Documentation must distinguish:

- manufacturer specification;
- common information from third-party boards;
- observation of our physical sample;
- hypothesis requiring verification.
