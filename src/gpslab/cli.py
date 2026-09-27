from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .diagnostics import GPSDiagnostics
from .serialio import (
    DEFAULT_BAUD_RATES,
    identify_ubx,
    list_serial_ports,
    open_serial,
    probe_port,
)


GROUPS = ("serial", "protocol", "receiver", "sat", "nav", "time", "status")


def _fmt(value, suffix: str = "") -> str:
    if value is None:
        return "-"
    return f"{value}{suffix}"


def _selected_groups(groups: list[str] | None, default: list[str] | None = None) -> list[str]:
    selected = list(groups or default or ["all"])
    if "all" in selected:
        return list(GROUPS)

    ordered = []
    for group in GROUPS:
        if group in selected and group not in ordered:
            ordered.append(group)
    return ordered


def _conclusion(state) -> str:
    if not state.has_data:
        return "NO DATA: check power, GND, TX/RX wiring and port."
    if not state.has_protocol:
        return "DATA PRESENT, protocol not validated: check baud rate."
    if state.fix == "NO FIX":
        if state.satellites_visible == 0:
            return "RECEIVER ALIVE - NO SATELLITES VISIBLE."
        if state.satellites_visible:
            return "SATELLITES VISIBLE - NO FIX YET."
        return "RECEIVER COMMUNICATION OK - NO FIX."
    if state.fix == "2D":
        return "RECEIVER COMMUNICATION OK - 2D FIX."
    if state.fix == "3D":
        return "RECEIVER COMMUNICATION OK - 3D FIX."
    return "RECEIVER COMMUNICATION AND NAVIGATION FIX OK."


def _print_heading(title: str) -> None:
    print()
    print(f"[ {title.upper()} ]")
    print("-" * 48)


def print_state(
    state,
    groups: list[str] | None = None,
    *,
    title: bool = True,
    default_groups: list[str] | None = None,
) -> None:
    selected = _selected_groups(groups, default_groups)

    if title:
        print()
        print("GPS Diagnostic Report")
        print("=" * 48)

    if "serial" in selected:
        _print_heading("serial")
        print(f"Port              : {_fmt(state.port)}")
        print(f"Baud              : {_fmt(state.baud)}")
        print(f"Bytes received    : {state.bytes_received}")

    if "protocol" in selected:
        _print_heading("protocol")
        print(f"Protocol          : {state.protocol}")
        print(f"NMEA valid        : {state.nmea_valid}")
        print(f"NMEA invalid      : {state.nmea_invalid}")
        print(f"UBX frames        : {state.ubx_frames}")

        if state.sentence_counts:
            counts = ", ".join(
                f"{key}:{value}"
                for key, value in sorted(state.sentence_counts.items())
            )
            print(f"NMEA messages     : {counts}")
        else:
            print("NMEA messages     : -")

    if "receiver" in selected:
        _print_heading("receiver")
        print(f"Receiver          : {_fmt(state.receiver_identity)}")
        print(f"UBX SW            : {_fmt(state.ubx_sw_version)}")
        print(f"UBX HW            : {_fmt(state.ubx_hw_version)}")

        if state.ubx_extensions:
            print("UBX extensions    :")
            for item in state.ubx_extensions:
                print(f"  - {item}")
        else:
            print("UBX extensions    : -")

    if "sat" in selected:
        _print_heading("satellites / fix")
        print(f"Fix               : {state.fix}")
        print(f"Satellites used   : {_fmt(state.satellites_used)}")
        print(f"Satellites visible: {_fmt(state.satellites_visible)}")
        print(f"HDOP              : {_fmt(state.hdop)}")

    if "nav" in selected:
        _print_heading("navigation")
        print(f"Latitude          : {_fmt(state.latitude)}")
        print(f"Longitude         : {_fmt(state.longitude)}")
        print(f"Altitude          : {_fmt(state.altitude_m, ' m')}")
        print(f"Speed             : {_fmt(state.speed_kmh, ' km/h')}")

    if "time" in selected:
        _print_heading("time / rate")
        print(f"UTC time          : {_fmt(state.utc_time)}")
        print(f"UTC date          : {_fmt(state.utc_date)}")
        if state.gga_rate_hz is not None:
            print(f"GGA rate          : {state.gga_rate_hz:.2f} Hz")
        else:
            print("GGA rate          : -")

    if "status" in selected:
        _print_heading("status")
        print(f"Conclusion        : {_conclusion(state)}")


def cmd_ports(_args) -> int:
    ports = list_serial_ports()
    if not ports:
        print("No serial ports found.")
        return 1

    print(f"{'PORT':<12} {'DESCRIPTION':<36} HWID")
    print("-" * 90)
    for item in ports:
        print(f"{item.device:<12} {item.description[:35]:<36} {item.hwid}")
    return 0


def cmd_probe(args) -> int:
    rates = [args.baud] if args.baud else DEFAULT_BAUD_RATES
    diag = probe_port(
        port=args.port,
        baud_rates=rates,
        seconds_per_baud=args.seconds,
        identify=not args.no_identify,
    )

    if args.json:
        print(json.dumps(diag.state.to_dict(), ensure_ascii=False, indent=2))
    else:
        print_state(diag.state, args.group)

    return 0 if diag.state.has_protocol else 2


def cmd_identify(args) -> int:
    diag = identify_ubx(args.port, args.baud, args.seconds)
    if args.json:
        print(json.dumps(diag.state.to_dict(), ensure_ascii=False, indent=2))
    else:
        print_state(diag.state, args.group)
    return 0 if diag.state.ubx_sw_version or diag.state.ubx_hw_version else 2


def cmd_monitor(args) -> int:
    diag = GPSDiagnostics(port=args.port, baud=args.baud)
    next_report = time.monotonic() + args.interval
    report_number = 0

    try:
        with open_serial(args.port, args.baud) as ser:
            print(
                f"Monitoring {args.port} at {args.baud} 8N1. "
                "Press Ctrl+C to stop."
            )

            while True:
                waiting = getattr(ser, "in_waiting", 0)
                chunk = ser.read(waiting or 256)
                if chunk:
                    diag.feed(chunk)
                    if args.raw:
                        sys.stdout.write(chunk.decode("ascii", "replace"))
                        sys.stdout.flush()

                if time.monotonic() >= next_report:
                    if not args.raw:
                        report_number += 1
                        print()
                        print(
                            f"Snapshot #{report_number} "
                            f"({time.strftime('%H:%M:%S')})"
                        )
                        print("=" * 48)
                        print_state(
                            diag.state,
                            args.group,
                            title=False,
                            default_groups=["sat", "nav", "time"],
                        )
                    next_report = time.monotonic() + args.interval

    except KeyboardInterrupt:
        print()
        print("Final state")
        print_state(
            diag.state,
            args.group,
            default_groups=["sat", "nav", "time", "status"],
        )
        return 0


def cmd_capture(args) -> int:
    path = Path(args.output)
    diag = GPSDiagnostics(port=args.port, baud=args.baud)

    with open_serial(args.port, args.baud) as ser, path.open("wb") as handle:
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            waiting = getattr(ser, "in_waiting", 0)
            chunk = ser.read(waiting or 256)
            if chunk:
                handle.write(chunk)
                diag.feed(chunk)

    print(f"Saved {diag.state.bytes_received} bytes to {path}")
    print_state(diag.state, args.group)
    return 0


def add_group_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-g",
        "--group",
        action="append",
        choices=("all",) + GROUPS,
        help=(
            "Output group. Repeat to combine groups. "
            "Choices: all, serial, protocol, receiver, sat, nav, time, status."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gps-cli",
        description="GPS/GNSS serial diagnostics for the GPS laboratory.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ports", help="List serial ports.")
    p.set_defaults(func=cmd_ports)

    p = sub.add_parser("probe", help="Auto-detect baud and GPS protocol.")
    p.add_argument("port", help="Serial port, for example COM7.")
    p.add_argument(
        "--baud",
        type=int,
        help="Test only this baud rate instead of auto-probing.",
    )
    p.add_argument(
        "--seconds",
        type=float,
        default=1.5,
        help="Passive sample time per baud rate.",
    )
    p.add_argument(
        "--no-identify",
        action="store_true",
        help="Do not send the read-only UBX MON-VER identity poll.",
    )
    p.add_argument("--json", action="store_true", help="JSON output.")
    add_group_argument(p)
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("identify", help="Poll u-blox UBX MON-VER.")
    p.add_argument("port")
    p.add_argument("--baud", type=int, default=9600)
    p.add_argument("--seconds", type=float, default=1.0)
    p.add_argument("--json", action="store_true")
    add_group_argument(p)
    p.set_defaults(func=cmd_identify)

    p = sub.add_parser("monitor", help="Live GPS status.")
    p.add_argument("port")
    p.add_argument("--baud", type=int, default=9600)
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument(
        "--raw",
        action="store_true",
        help="Print the raw serial stream.",
    )
    add_group_argument(p)
    p.set_defaults(func=cmd_monitor)

    p = sub.add_parser("capture", help="Save raw serial data.")
    p.add_argument("port")
    p.add_argument("--baud", type=int, default=9600)
    p.add_argument("--seconds", type=float, default=30.0)
    p.add_argument("--output", default="gps-capture.bin")
    add_group_argument(p)
    p.set_defaults(func=cmd_capture)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
