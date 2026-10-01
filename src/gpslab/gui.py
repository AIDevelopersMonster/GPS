from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .diagnostics import GPSDiagnostics
from .nmea import explain_sentence, parse_sentence
from .registry import (
    DEFAULT_DB,
    add_inspection,
    db_status,
    ensure_db,
    export_json,
    find_inspection_by_rinv,
    get_inspection,
    preview_next_module_code,
    update_inspection,
    utc_now_iso,
)
from .registry_reports import (
    backup_database,
    export_csv,
    generate_html_report,
    query_inspections,
    registry_summary,
)
from .serialio import DEFAULT_BAUD_RATES, list_serial_ports, open_serial, probe_port
from .timecheck import utc_delta_seconds
from .ubx import (
    CFG_RINV_POLL,
    CFG_USB_POLL,
    build_cfg_cfg_save_rinv,
    build_cfg_rinv_write,
    MON_HW_POLL,
    MON_IO_POLL,
    MON_RXBUF_POLL,
    MON_TXBUF_POLL,
    MON_VER_POLL,
    NAV_TIMEUTC_POLL,
    SEC_UNIQID_POLL,
    frame_name,
    packet_is_valid,
)


class SerialWorker(threading.Thread):
    def __init__(self, port: str, baud: int, events: queue.Queue):
        super().__init__(daemon=True)
        self.port = port
        self.baud = baud
        self.events = events
        self.stop_event = threading.Event()
        self.tx_queue: queue.Queue[bytes] = queue.Queue()

    def send(self, data: bytes) -> None:
        self.tx_queue.put(data)

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        try:
            with open_serial(self.port, self.baud, timeout=0.1) as ser:
                self.events.put(("connected", None))
                while not self.stop_event.is_set():
                    while True:
                        try:
                            packet = self.tx_queue.get_nowait()
                        except queue.Empty:
                            break
                        ser.write(packet)
                        ser.flush()
                        self.events.put(("tx", packet))

                    waiting = getattr(ser, "in_waiting", 0)
                    chunk = ser.read(waiting or 256)
                    if chunk:
                        self.events.put(("data", chunk))

                self.events.put(("disconnected", None))
        except Exception as exc:
            self.events.put(("error", str(exc)))


class GPSGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GPS Lab Diagnostic Console v0.6")
        self.geometry("1080x760")
        self.minsize(900, 640)

        self.events: queue.Queue = queue.Queue()
        self.worker: SerialWorker | None = None
        self.diag = GPSDiagnostics()
        self.capture_file = None
        self.auto_probe_thread: threading.Thread | None = None

        self.port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value="9600")
        self.connection_var = tk.StringVar(value="DISCONNECTED")
        self.status_var = tk.StringVar(value="NO DATA")
        self.protocol_var = tk.StringVar(value="NONE")
        self.receiver_var = tk.StringVar(value="-")
        self.sw_var = tk.StringVar(value="-")
        self.hw_var = tk.StringVar(value="-")
        self.mon_ver_status_var = tk.StringVar(value="NOT REQUESTED")
        self.protver_var = tk.StringVar(value="-")
        self.serial_var = tk.StringVar(value="-")
        self.unique_var = tk.StringVar(value="-")
        self.rinv_status_var = tk.StringVar(value="NOT READ")
        self.rinv_text_var = tk.StringVar(value="-")
        self.rinv_hex_var = tk.StringVar(value="-")
        self.fix_var = tk.StringVar(value="NO FIX")
        self.sats_used_var = tk.StringVar(value="-")
        self.sats_visible_var = tk.StringVar(value="-")
        self.hdop_var = tk.StringVar(value="-")
        self.lat_var = tk.StringVar(value="-")
        self.lon_var = tk.StringVar(value="-")
        self.alt_var = tk.StringVar(value="-")
        self.utc_var = tk.StringVar(value="-")
        self.gnss_time_var = tk.StringVar(value="-")
        self.gnss_date_var = tk.StringVar(value="-")
        self.system_utc_var = tk.StringVar(value="-")
        self.time_primary_var = tk.StringVar(value="GNSS UTC: waiting...")
        self.host_utc_delta_var = tk.StringVar(value="-")
        self.time_status_var = tk.StringVar(value="WAITING")
        self.ubx_time_var = tk.StringVar(value="-")
        self.ubx_time_valid_var = tk.StringVar(value="NOT CHECKED")
        self.rate_var = tk.StringVar(value="-")
        self.bytes_var = tk.StringVar(value="0")
        self.ubx_hex_var = tk.StringVar()

        self.db_path_var = tk.StringVar(value=str(DEFAULT_DB))
        self.db_status_var = tk.StringVar(value="NOT CHECKED")
        self.db_records_var = tk.StringVar(value="0")
        self.registry_next_var = tk.StringVar(value="-")
        self.registry_rinv_var = tk.StringVar(value="-")
        self.registry_state_var = tk.StringVar(value="IDLE")
        self.registry_last_var = tk.StringVar(value="-")
        self.registry_filter_var = tk.StringVar()
        self.registry_result_filter_var = tk.StringVar(value="ALL")
        self.registry_summary_var = tk.StringVar(value="-")

        self._build_ui()
        self.refresh_ports()
        self._refresh_registry_status()
        self.after(100, self._poll_events)

    def _build_ui(self) -> None:
        controls = ttk.Frame(self, padding=8)
        controls.pack(fill="x")

        ttk.Label(controls, text="Port").grid(row=0, column=0, sticky="w")
        self.port_combo = ttk.Combobox(
            controls, textvariable=self.port_var, width=14, state="normal"
        )
        self.port_combo.grid(row=0, column=1, padx=(4, 10))

        ttk.Button(controls, text="Refresh", command=self.refresh_ports).grid(
            row=0, column=2, padx=(0, 10)
        )

        ttk.Label(controls, text="Baud").grid(row=0, column=3, sticky="w")
        self.baud_combo = ttk.Combobox(
            controls,
            textvariable=self.baud_var,
            values=[str(x) for x in DEFAULT_BAUD_RATES],
            width=9,
            state="normal",
        )
        self.baud_combo.grid(row=0, column=4, padx=(4, 10))

        ttk.Button(controls, text="Auto Probe", command=self.auto_probe).grid(
            row=0, column=5, padx=4
        )

        self.connect_button = ttk.Button(
            controls, text="Connect", command=self.toggle_connection
        )
        self.connect_button.grid(row=0, column=6, padx=4)

        ttk.Button(controls, text="Identify", command=self.identify_all).grid(
            row=0, column=7, padx=4
        )

        self.capture_button = ttk.Button(
            controls, text="Start Capture", command=self.toggle_capture
        )
        self.capture_button.grid(row=0, column=8, padx=4)

        ttk.Label(
            controls,
            textvariable=self.connection_var,
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=1, column=0, columnspan=9, sticky="w", pady=(8, 0))

        ttk.Label(
            controls,
            textvariable=self.status_var,
            font=("TkDefaultFont", 12, "bold"),
        ).grid(row=2, column=0, columnspan=9, sticky="w", pady=(4, 0))

        ttk.Label(
            controls,
            textvariable=self.time_primary_var,
            font=("TkDefaultFont", 15, "bold"),
        ).grid(row=3, column=0, columnspan=9, sticky="w", pady=(6, 2))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        overview = ttk.Frame(notebook, padding=12)
        identity = ttk.Frame(notebook, padding=12)
        engineering = ttk.Frame(notebook, padding=8)
        registry = ttk.Frame(notebook, padding=8)
        ubx_terminal = ttk.Frame(notebook, padding=8)
        nmea = ttk.Frame(notebook, padding=6)
        raw = ttk.Frame(notebook, padding=6)

        notebook.add(overview, text="Overview")
        notebook.add(identity, text="Identity / Time")
        notebook.add(nmea, text="NMEA Decoder")
        notebook.add(engineering, text="Engineering")
        notebook.add(registry, text="Registry / Provisioning")
        notebook.add(ubx_terminal, text="UBX Terminal")
        notebook.add(raw, text="Raw Stream")

        fields = [
            ("Protocol", self.protocol_var),
            ("Receiver", self.receiver_var),
            ("Fix", self.fix_var),
            ("Satellites used", self.sats_used_var),
            ("Satellites visible", self.sats_visible_var),
            ("HDOP", self.hdop_var),
            ("Latitude", self.lat_var),
            ("Longitude", self.lon_var),
            ("Altitude", self.alt_var),
            ("GNSS time UTC", self.gnss_time_var),
            ("GNSS date UTC", self.gnss_date_var),
            ("NMEA UTC raw/combined", self.utc_var),
            ("System UTC", self.system_utc_var),
            ("UBX UTC", self.ubx_time_var),
            ("UBX UTC validity", self.ubx_time_valid_var),
            ("Host UTC delta", self.host_utc_delta_var),
            ("Time status", self.time_status_var),
            ("GGA rate", self.rate_var),
            ("Bytes received", self.bytes_var),
        ]

        for row, (label, var) in enumerate(fields):
            ttk.Label(overview, text=label + ":").grid(
                row=row, column=0, sticky="w", padx=(0, 16), pady=3
            )
            ttk.Label(
                overview,
                textvariable=var,
                font=("TkDefaultFont", 10, "bold"),
            ).grid(row=row, column=1, sticky="w", pady=3)

        identity_box = ttk.LabelFrame(
            identity, text="Receiver identification", padding=10
        )
        identity_box.pack(fill="x", pady=(0, 10))

        identity_fields = [
            ("Receiver", self.receiver_var),
            ("SW version", self.sw_var),
            ("HW version", self.hw_var),
            ("MON-VER status", self.mon_ver_status_var),
            ("Protocol version", self.protver_var),
            ("USB serial descriptor", self.serial_var),
            ("Unique chip ID", self.unique_var),
            ("Remote Inventory status", self.rinv_status_var),
            ("Remote Inventory text", self.rinv_text_var),
            ("Remote Inventory hex", self.rinv_hex_var),
        ]

        for row, (label, var) in enumerate(identity_fields):
            ttk.Label(identity_box, text=label + ":").grid(
                row=row, column=0, sticky="w", padx=(0, 16), pady=3
            )
            ttk.Label(
                identity_box,
                textvariable=var,
                font=("TkDefaultFont", 10, "bold"),
            ).grid(row=row, column=1, sticky="w", pady=3)

        ttk.Label(
            identity_box,
            text=(
                "USB serial descriptor is a USB descriptor string and is not guaranteed "
                "to be a factory-unique serial number. Unique chip ID is shown only if "
                "the receiver implements UBX-SEC-UNIQID."
            ),
            wraplength=940,
            justify="left",
        ).grid(row=len(identity_fields), column=0, columnspan=2, sticky="w", pady=(8, 0))

        time_box = ttk.LabelFrame(identity, text="Time", padding=10)
        time_box.pack(fill="x", pady=(0, 10))

        time_fields = [
            ("GNSS time UTC", self.gnss_time_var),
            ("GNSS date UTC", self.gnss_date_var),
            ("NMEA UTC combined", self.utc_var),
            ("System UTC", self.system_utc_var),
            ("UBX NAV-TIMEUTC", self.ubx_time_var),
            ("UBX UTC validity", self.ubx_time_valid_var),
            ("Host UTC delta", self.host_utc_delta_var),
            ("Time status", self.time_status_var),
        ]

        for row, (label, var) in enumerate(time_fields):
            ttk.Label(time_box, text=label + ":").grid(
                row=row, column=0, sticky="w", padx=(0, 16), pady=3
            )
            ttk.Label(
                time_box,
                textvariable=var,
                font=("TkDefaultFont", 10, "bold"),
            ).grid(row=row, column=1, sticky="w", pady=3)

        polls = ttk.LabelFrame(identity, text="Read-only UBX diagnostic requests", padding=10)
        polls.pack(fill="x")

        poll_rows = [
            (
                "Poll MON-VER",
                self._poll_mon_ver,
                "Read receiver software/hardware version and protocol information.",
            ),
            (
                "Poll CFG-USB",
                self._poll_cfg_usb,
                "Read USB descriptor configuration, including serial descriptor if present.",
            ),
            (
                "Poll SEC-UNIQID",
                self._poll_unique_id,
                "Request unique chip ID. Older receivers such as u-blox 6 may not support it.",
            ),
            (
                "Poll NAV-TIMEUTC",
                self._poll_timeutc,
                "Read UBX UTC time and its validity flags independently of NMEA display.",
            ),
            (
                "Read CFG-RINV",
                self._poll_rinv,
                "Read the receiver Remote Inventory field without writing anything.",
            ),
        ]

        for row, (caption, command, explanation) in enumerate(poll_rows):
            ttk.Button(polls, text=caption, command=command, width=18).grid(
                row=row, column=0, sticky="w", pady=3
            )
            ttk.Label(
                polls,
                text=explanation,
                wraplength=760,
                justify="left",
            ).grid(row=row, column=1, sticky="w", padx=(12, 0), pady=3)

        eng_controls = ttk.LabelFrame(
            engineering, text="Read-only u-blox monitor polls", padding=10
        )
        eng_controls.pack(fill="x", pady=(0, 8))

        poll_specs = [
            ("MON-HW", MON_HW_POLL, "RF/hardware state: noise, AGC, antenna and jamming indicators."),
            ("MON-IO", MON_IO_POLL, "I/O counters and serial-port errors."),
            ("MON-RXBUF", MON_RXBUF_POLL, "Receive-buffer load by target."),
            ("MON-TXBUF", MON_TXBUF_POLL, "Transmit-buffer load and allocation errors."),
        ]
        for col, (caption, packet, help_text) in enumerate(poll_specs):
            ttk.Button(
                eng_controls,
                text=caption,
                command=lambda p=packet: self._send_named(p),
                width=14,
            ).grid(row=0, column=col, padx=(0, 6), pady=2, sticky="w")
            ttk.Label(
                eng_controls,
                text=help_text,
                wraplength=225,
                justify="left",
            ).grid(row=1, column=col, padx=(0, 6), sticky="nw")

        ttk.Button(
            eng_controls,
            text="Poll All",
            command=self._poll_engineering_all,
            width=14,
        ).grid(row=2, column=0, pady=(8, 0), sticky="w")

        self.eng_hw_vars = {
            "Payload bytes": tk.StringVar(value="-"),
            "Noise / ms": tk.StringVar(value="-"),
            "AGC count": tk.StringVar(value="-"),
            "Antenna status": tk.StringVar(value="-"),
            "Antenna power": tk.StringVar(value="-"),
            "Jamming indicator": tk.StringVar(value="-"),
            "Jamming state": tk.StringVar(value="-"),
            "RTC calibrated": tk.StringVar(value="-"),
            "Safe boot": tk.StringVar(value="-"),
        }

        hw_box = ttk.LabelFrame(engineering, text="MON-HW / RF and hardware", padding=10)
        hw_box.pack(fill="x", pady=(0, 8))
        for row, (label, var) in enumerate(self.eng_hw_vars.items()):
            ttk.Label(hw_box, text=label + ":").grid(
                row=row, column=0, sticky="w", padx=(0, 14), pady=2
            )
            ttk.Label(
                hw_box, textvariable=var, font=("TkDefaultFont", 10, "bold")
            ).grid(row=row, column=1, sticky="w", pady=2)

        ttk.Label(
            hw_box,
            text=(
                "Jamming values are receiver diagnostic indicators. They can show RF "
                "interference conditions but do not by themselves identify a source or prove spoofing."
            ),
            wraplength=940,
            justify="left",
        ).grid(row=len(self.eng_hw_vars), column=0, columnspan=2, sticky="w", pady=(8, 0))

        io_box = ttk.LabelFrame(engineering, text="MON-IO / ports", padding=6)
        io_box.pack(fill="both", expand=True, pady=(0, 8))
        self.eng_io_tree = ttk.Treeview(
            io_box,
            columns=("port", "rx", "tx", "parity", "framing", "overrun", "rx_busy", "tx_busy"),
            show="headings",
            height=6,
        )
        for key, title, width in (
            ("port", "Port", 110),
            ("rx", "RX bytes", 100),
            ("tx", "TX bytes", 100),
            ("parity", "Parity", 80),
            ("framing", "Framing", 80),
            ("overrun", "Overrun", 80),
            ("rx_busy", "RX busy", 80),
            ("tx_busy", "TX busy", 80),
        ):
            self.eng_io_tree.heading(key, text=title)
            self.eng_io_tree.column(key, width=width, anchor="center")
        self.eng_io_tree.pack(fill="x")

        buffers = ttk.Frame(engineering)
        buffers.pack(fill="both", expand=True)
        rx_box = ttk.LabelFrame(buffers, text="MON-RXBUF", padding=6)
        tx_box = ttk.LabelFrame(buffers, text="MON-TXBUF", padding=6)
        rx_box.pack(side="left", fill="both", expand=True, padx=(0, 4))
        tx_box.pack(side="left", fill="both", expand=True, padx=(4, 0))

        self.eng_rx_tree = ttk.Treeview(
            rx_box, columns=("target", "pending", "usage", "peak"), show="headings", height=6
        )
        self.eng_tx_tree = ttk.Treeview(
            tx_box, columns=("target", "pending", "usage", "peak"), show="headings", height=6
        )
        for tree in (self.eng_rx_tree, self.eng_tx_tree):
            for key, title, width in (
                ("target", "Target", 110),
                ("pending", "Pending", 90),
                ("usage", "Usage %", 90),
                ("peak", "Peak %", 90),
            ):
                tree.heading(key, text=title)
                tree.column(key, width=width, anchor="center")
            tree.pack(fill="both", expand=True)

        self.eng_tx_status_var = tk.StringVar(value="TX buffer status: -")
        ttk.Label(
            tx_box, textvariable=self.eng_tx_status_var, font=("TkDefaultFont", 9, "bold")
        ).pack(anchor="w", pady=(6, 0))

        db_box = ttk.LabelFrame(registry, text="Local inspection database", padding=10)
        db_box.pack(fill="x", pady=(0, 10))

        db_rows = [
            ("Path", self.db_path_var),
            ("Physical file status", self.db_status_var),
            ("Records", self.db_records_var),
        ]
        for row, (label, var) in enumerate(db_rows):
            ttk.Label(db_box, text=label + ":").grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=3
            )
            ttk.Label(
                db_box, textvariable=var, font=("TkDefaultFont", 10, "bold")
            ).grid(row=row, column=1, sticky="w", pady=3)

        ttk.Button(
            db_box, text="Check database", command=self._refresh_registry_status
        ).grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Button(
            db_box, text="Create database", command=self._create_registry_db
        ).grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Button(
            db_box, text="Export JSON", command=self._export_registry_json
        ).grid(row=3, column=2, sticky="w", padx=(8, 0), pady=(8, 0))

        ttk.Label(
            db_box,
            text=(
                "The status check never creates the database. If the SQLite file is absent, "
                "the GUI reports NOT CREATED. Creation happens only after pressing Create database."
            ),
            wraplength=920,
            justify="left",
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))

        prov_box = ttk.LabelFrame(registry, text="Technological module record", padding=10)
        prov_box.pack(fill="x", pady=(0, 10))

        prov_rows = [
            ("Next module number", self.registry_next_var),
            ("Planned CFG-RINV text", self.registry_rinv_var),
            ("Provisioning state", self.registry_state_var),
            ("Last result", self.registry_last_var),
        ]
        for row, (label, var) in enumerate(prov_rows):
            ttk.Label(prov_box, text=label + ":").grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=3
            )
            ttk.Label(
                prov_box, textvariable=var, font=("TkDefaultFont", 10, "bold")
            ).grid(row=row, column=1, sticky="w", pady=3)

        ttk.Button(
            prov_box, text="Preview next ID", command=self._preview_registry_id
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Button(
            prov_box, text="Provision tested module", command=self._provision_current_module
        ).grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Button(
            prov_box, text="Verify after power cycle", command=self._verify_persisted_module
        ).grid(row=4, column=2, sticky="w", padx=(8, 0), pady=(8, 0))

        ttk.Label(
            prov_box,
            text=(
                "Provision writes a plain human-readable marker only after RINV is confirmed empty "
                "and GNSS/NMEA time has been received. SW/HW, fix and Engineering/MON data are optional: "
                "they are stored if already available, but provisioning never waits for them. "
                "Final PASS requires the marker to survive a power cycle and time to be received again."
            ),
            wraplength=920,
            justify="left",
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))

        manager_box = ttk.LabelFrame(registry, text="Registry manager", padding=10)
        manager_box.pack(fill="both", expand=True)

        filter_row = ttk.Frame(manager_box)
        filter_row.pack(fill="x", pady=(0, 6))
        ttk.Label(filter_row, text="Module contains").pack(side="left")
        ttk.Entry(filter_row, textvariable=self.registry_filter_var, width=24).pack(
            side="left", padx=(6, 12)
        )
        ttk.Label(filter_row, text="Result").pack(side="left")
        ttk.Combobox(
            filter_row,
            textvariable=self.registry_result_filter_var,
            values=("ALL", "PASS", "PENDING", "PENDING_POWER_CYCLE", "WRITE_VERIFY_FAILED"),
            width=24,
            state="readonly",
        ).pack(side="left", padx=(6, 12))
        ttk.Button(filter_row, text="Refresh", command=self._refresh_registry_table).pack(side="left")
        ttk.Button(filter_row, text="Summary", command=self._show_registry_summary).pack(
            side="left", padx=(6, 0)
        )

        self.registry_tree = ttk.Treeview(
            manager_box,
            columns=("id", "module", "utc", "result", "profile", "receiver"),
            show="headings",
            height=7,
        )
        for key, title, width in (
            ("id", "ID", 55),
            ("module", "Module", 170),
            ("utc", "Tested UTC", 175),
            ("result", "Result", 170),
            ("profile", "Profile", 130),
            ("receiver", "Receiver", 190),
        ):
            self.registry_tree.heading(key, text=title)
            self.registry_tree.column(key, width=width, anchor="w")
        self.registry_tree.pack(fill="both", expand=True)

        action_row = ttk.Frame(manager_box)
        action_row.pack(fill="x", pady=(8, 0))
        ttk.Button(action_row, text="Show record", command=self._show_selected_registry_record).pack(side="left")
        ttk.Button(action_row, text="Export CSV", command=self._export_registry_csv).pack(side="left", padx=(6, 0))
        ttk.Button(action_row, text="HTML report", command=self._export_registry_html).pack(side="left", padx=(6, 0))
        ttk.Button(action_row, text="Backup DB", command=self._backup_registry_db).pack(side="left", padx=(6, 0))
        ttk.Label(
            action_row,
            textvariable=self.registry_summary_var,
            font=("TkDefaultFont", 9, "bold"),
        ).pack(side="right")

        self._refresh_registry_table()

        self.nmea_notebook = ttk.Notebook(nmea)
        self.nmea_notebook.pack(fill="both", expand=True)
        self.nmea_views = {}

        for message_type in ("GGA", "RMC", "GSA", "GSV", "GLL", "VTG", "TXT"):
            frame = ttk.Frame(self.nmea_notebook, padding=8)
            self.nmea_notebook.add(frame, text=f"GP{message_type}")

            summary_var = tk.StringVar(value="Waiting for message...")
            raw_var = tk.StringVar(value="-")
            status_var = tk.StringVar(value="No data")

            ttk.Label(
                frame,
                textvariable=summary_var,
                font=("TkDefaultFont", 10, "bold"),
                wraplength=940,
                justify="left",
            ).pack(anchor="w")

            ttk.Label(
                frame,
                textvariable=status_var,
                font=("TkDefaultFont", 9, "bold"),
            ).pack(anchor="w", pady=(4, 6))

            raw_box = ttk.LabelFrame(frame, text="Raw NMEA sentence", padding=6)
            raw_box.pack(fill="x", pady=(0, 8))
            ttk.Label(
                raw_box,
                textvariable=raw_var,
                font=("Consolas", 9),
                wraplength=940,
                justify="left",
            ).pack(anchor="w")

            tree_frame = ttk.Frame(frame)
            tree_frame.pack(fill="both", expand=True)

            tree = ttk.Treeview(
                tree_frame,
                columns=("field", "raw", "decoded", "meaning"),
                show="headings",
                height=18,
            )
            tree.heading("field", text="Field")
            tree.heading("raw", text="Raw")
            tree.heading("decoded", text="Decoded")
            tree.heading("meaning", text="What it means")
            tree.column("field", width=150, anchor="w")
            tree.column("raw", width=160, anchor="w")
            tree.column("decoded", width=210, anchor="w")
            tree.column("meaning", width=460, anchor="w")

            y = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
            x = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
            tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
            tree.grid(row=0, column=0, sticky="nsew")
            y.grid(row=0, column=1, sticky="ns")
            x.grid(row=1, column=0, sticky="ew")
            tree_frame.rowconfigure(0, weight=1)
            tree_frame.columnconfigure(0, weight=1)

            self.nmea_views[message_type] = {
                "summary": summary_var,
                "raw": raw_var,
                "status": status_var,
                "tree": tree,
            }

        terminal_controls = ttk.Frame(ubx_terminal)
        terminal_controls.pack(fill="x")

        ttk.Label(terminal_controls, text="UBX packet hex").pack(side="left")
        ttk.Entry(
            terminal_controls,
            textvariable=self.ubx_hex_var,
            width=70,
            font=("Consolas", 9),
        ).pack(side="left", padx=8, fill="x", expand=True)
        ttk.Button(
            terminal_controls,
            text="Send",
            command=self.send_terminal_packet,
        ).pack(side="left")

        ttk.Label(
            ubx_terminal,
            text="Only complete UBX packets with valid checksum are transmitted.",
        ).pack(anchor="w", pady=(6, 4))

        self.ubx_text = tk.Text(
            ubx_terminal, wrap="none", font=("Consolas", 9), state="disabled"
        )
        self.ubx_text.pack(fill="both", expand=True)

        raw_controls = ttk.Frame(raw)
        raw_controls.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Button(
            raw_controls,
            text="Clear Log",
            command=self._clear_raw_stream,
        ).pack(side="left")

        self.raw_text = tk.Text(
            raw, wrap="none", font=("Consolas", 9), state="disabled"
        )
        ybar = ttk.Scrollbar(raw, orient="vertical", command=self.raw_text.yview)
        xbar = ttk.Scrollbar(raw, orient="horizontal", command=self.raw_text.xview)
        self.raw_text.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.raw_text.grid(row=1, column=0, sticky="nsew")
        ybar.grid(row=1, column=1, sticky="ns")
        xbar.grid(row=2, column=0, sticky="ew")
        raw.rowconfigure(1, weight=1)
        raw.columnconfigure(0, weight=1)

    def refresh_ports(self) -> None:
        try:
            ports = list_serial_ports()
        except Exception as exc:
            messagebox.showerror("GPS Lab", str(exc))
            return

        values = [item.device for item in ports]
        self.port_combo["values"] = values
        if values and not self.port_var.get():
            self.port_var.set(values[0])

    def toggle_connection(self) -> None:
        if self.worker and self.worker.is_alive():
            self.disconnect()
        else:
            self.connect()

    def connect(self) -> None:
        port = self.port_var.get().strip()
        if not port:
            messagebox.showwarning("GPS Lab", "Select a serial port.")
            return

        try:
            baud = int(self.baud_var.get())
        except ValueError:
            messagebox.showwarning("GPS Lab", "Invalid baud rate.")
            return

        self.diag = GPSDiagnostics(port=port, baud=baud)
        self.worker = SerialWorker(port, baud, self.events)
        self.worker.start()
        self.connection_var.set(f"CONNECTING: {port} @ {baud}")
        self.connect_button.configure(text="Disconnect")

    def disconnect(self) -> None:
        if self.worker:
            self.worker.stop()
        self.worker = None
        self.connect_button.configure(text="Connect")
        self.connection_var.set("DISCONNECTED")
        self._stop_capture()

    def _ensure_connected(self) -> bool:
        if not self.worker or not self.worker.is_alive():
            messagebox.showinfo("GPS Lab", "Connect to the receiver first.")
            return False
        return True

    def _send_named(self, packet: bytes) -> None:
        if not self._ensure_connected():
            return
        self.worker.send(packet)

    def _mark_identity_no_response(self) -> None:
        s = self.diag.state
        if s.usb_serial_number is None and self.serial_var.get() == "polling...":
            self.serial_var.set("not returned / descriptor unavailable")
        if s.unique_id is None and self.unique_var.get() == "polling...":
            self.unique_var.set("not returned / unsupported by this receiver")

    def _poll_mon_ver(self) -> None:
        if not self._ensure_connected():
            return
        self.mon_ver_status_var.set("REQUESTED")
        self.worker.send(MON_VER_POLL)
        self.after(450, lambda: self._request_mon_ver_retry(1))

    def _request_mon_ver_retry(self, attempt: int) -> None:
        if not self.worker or not self.worker.is_alive():
            return
        s = self.diag.state
        if s.ubx_sw_version or s.ubx_hw_version:
            self.mon_ver_status_var.set("RECEIVED")
            return
        if attempt >= 3:
            self.mon_ver_status_var.set("NO RESPONSE")
            return
        self.mon_ver_status_var.set(f"REQUESTED {attempt + 1}/3")
        self.worker.send(MON_VER_POLL)
        delay = (350, 550, 800)[attempt]
        self.after(delay, lambda a=attempt + 1: self._request_mon_ver_retry(a))

    def _poll_cfg_usb(self) -> None:
        if not self._ensure_connected():
            return
        self.serial_var.set("polling...")
        self.worker.send(CFG_USB_POLL)
        self.after(1500, self._mark_identity_no_response)

    def _poll_unique_id(self) -> None:
        if not self._ensure_connected():
            return
        self.unique_var.set("polling...")
        self.worker.send(SEC_UNIQID_POLL)
        self.after(1500, self._mark_identity_no_response)

    def _poll_timeutc(self) -> None:
        self._send_named(NAV_TIMEUTC_POLL)

    def _poll_rinv(self) -> None:
        if not self._ensure_connected():
            return
        self.rinv_status_var.set("READING...")
        self.rinv_text_var.set("-")
        self.rinv_hex_var.set("-")
        self.worker.send(CFG_RINV_POLL)

    def identify_all(self) -> None:
        if not self._ensure_connected():
            return

        # Stagger requests. Five back-to-back polls on a 9600-baud receiver
        # compete with the continuous NMEA stream and can make an old u-blox 6
        # response easy to miss. MON-VER is intentionally first.
        self.mon_ver_status_var.set("REQUESTED")
        self.serial_var.set("polling...")
        self.unique_var.set("polling...")
        self.worker.send(MON_VER_POLL)
        self.after(180, lambda: self.worker and self.worker.send(NAV_TIMEUTC_POLL))
        self.after(360, lambda: self.worker and self.worker.send(CFG_RINV_POLL))
        self.after(650, lambda: self.worker and self.worker.send(CFG_USB_POLL))
        self.after(1050, lambda: self.worker and self.worker.send(SEC_UNIQID_POLL))
        self.after(450, lambda: self._request_mon_ver_retry(1))
        self.connection_var.set(
            self.connection_var.get() + " | identity sequence sent"
        )
        self.after(1800, self._mark_identity_no_response)

    def _refresh_registry_table(self) -> None:
        if not hasattr(self, "registry_tree"):
            return
        for item in self.registry_tree.get_children():
            self.registry_tree.delete(item)

        rows = query_inspections(
            module_contains=self.registry_filter_var.get().strip() or None,
            result=self.registry_result_filter_var.get(),
            limit=500,
            db_path=DEFAULT_DB,
        )
        for row in rows:
            self.registry_tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                values=(
                    row.get("id"),
                    row.get("module_code"),
                    row.get("tested_at_utc"),
                    row.get("result"),
                    row.get("profile"),
                    row.get("receiver"),
                ),
            )

        summary = registry_summary(DEFAULT_DB)
        results = summary.get("results") or {}
        self.registry_summary_var.set(
            f"Records: {(summary.get('database') or {}).get('records', 0)} | "
            + " | ".join(f"{k}: {v}" for k, v in results.items())
        )

    def _selected_registry_module(self) -> str | None:
        selection = self.registry_tree.selection()
        if not selection:
            messagebox.showinfo("GPS Lab Registry", "Select a record first.")
            return None
        values = self.registry_tree.item(selection[0], "values")
        return str(values[1]) if len(values) > 1 else None

    def _show_selected_registry_record(self) -> None:
        module_code = self._selected_registry_module()
        if not module_code:
            return
        item = get_inspection(module_code, DEFAULT_DB)
        if item is None:
            messagebox.showerror("GPS Lab Registry", f"Record not found: {module_code}")
            return

        win = tk.Toplevel(self)
        win.title(f"Registry record - {module_code}")
        win.geometry("900x650")
        text = tk.Text(win, wrap="word", font=("Consolas", 9))
        text.pack(fill="both", expand=True)
        import json
        text.insert("1.0", json.dumps(item, ensure_ascii=False, indent=2, sort_keys=True))
        text.configure(state="disabled")

    def _show_registry_summary(self) -> None:
        summary = registry_summary(DEFAULT_DB)
        import json
        messagebox.showinfo(
            "GPS Lab Registry Summary",
            json.dumps(summary, ensure_ascii=False, indent=2),
        )

    def _export_registry_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export registry CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        rows = query_inspections(
            module_contains=self.registry_filter_var.get().strip() or None,
            result=self.registry_result_filter_var.get(),
            limit=1000000,
            db_path=DEFAULT_DB,
        )
        out = export_csv(Path(path), db_path=DEFAULT_DB, rows=rows)
        self.registry_last_var.set(f"CSV exported: {out}")

    def _export_registry_html(self) -> None:
        module_code = None
        selection = self.registry_tree.selection()
        if selection:
            values = self.registry_tree.item(selection[0], "values")
            if len(values) > 1:
                module_code = str(values[1])

        path = filedialog.asksaveasfilename(
            title="Save HTML report",
            defaultextension=".html",
            filetypes=[("HTML", "*.html"), ("All files", "*.*")],
        )
        if not path:
            return
        out = generate_html_report(Path(path), module_code=module_code, db_path=DEFAULT_DB)
        self.registry_last_var.set(f"HTML report: {out}")

    def _backup_registry_db(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Backup GPS Lab database",
            defaultextension=".sqlite3",
            filetypes=[("SQLite", "*.sqlite3"), ("All files", "*.*")],
        )
        if not path:
            return
        out = backup_database(Path(path), DEFAULT_DB)
        self.registry_last_var.set(f"Database backup: {out}")

    def _refresh_registry_status(self) -> None:
        status = db_status(DEFAULT_DB)
        self.db_path_var.set(status["path"])
        if status.get("exists"):
            if status.get("error"):
                self.db_status_var.set("ERROR: " + str(status["error"]))
            else:
                self.db_status_var.set(
                    f"EXISTS | {status.get('size_bytes', 0)} bytes | schema {status.get('schema_version')}"
                )
            self.db_records_var.set(str(status.get("records", 0)))
        else:
            self.db_status_var.set("NOT CREATED")
            self.db_records_var.set("0")
        self._preview_registry_id()
        self._refresh_registry_table()

    def _create_registry_db(self) -> None:
        path = ensure_db(DEFAULT_DB)
        self.registry_last_var.set(f"Database created/opened: {path}")
        self._refresh_registry_status()

    def _export_registry_json(self) -> None:
        status = db_status(DEFAULT_DB)
        if not status.get("exists"):
            messagebox.showinfo("GPS Lab Registry", "Database does not exist yet.")
            return
        path = filedialog.asksaveasfilename(
            title="Export GPS Lab registry as JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        out = export_json(Path(path), DEFAULT_DB)
        self.registry_last_var.set(f"Exported: {out}")

    def _preview_registry_id(self) -> None:
        tested_at = utc_now_iso()
        module_code = preview_next_module_code(tested_at, DEFAULT_DB)
        self.registry_next_var.set(module_code)
        from .registry import build_rinv_text
        self.registry_rinv_var.set(build_rinv_text(module_code, tested_at))

    def _current_test_snapshot(self) -> tuple[bool, dict]:
        s = self.diag.state

        # Fast technological profile: receiving GNSS/NMEA time is the only
        # mandatory functional observation. Everything else is opportunistic
        # engineering data and is stored if it happened to arrive.
        required = {
            "time_received": bool(s.utc_time),
        }

        uart_errors = None
        for row in s.mon_io:
            if row.get("name") == "UART1":
                uart_errors = [
                    int(row.get("parity_errs", 0)),
                    int(row.get("framing_errs", 0)),
                    int(row.get("overrun_errs", 0)),
                ]
                break

        optional = {
            "serial_data": s.bytes_received > 0,
            "nmea_valid_frames": s.nmea_valid,
            "nmea_invalid_frames": s.nmea_invalid,
            "ubx_frames": s.ubx_frames,
            "sw_version": s.ubx_sw_version,
            "hw_version": s.ubx_hw_version,
            "receiver_identity": s.receiver_identity,
            "fix": s.fix,
            "satellites_used": s.satellites_used,
            "mon_hw_received": bool(s.mon_hw),
            "antenna_status": (s.mon_hw or {}).get("antenna_status"),
            "mon_io_received": bool(s.mon_io),
            "uart_errors": uart_errors,
            "rxbuf_received": bool(s.mon_rxbuf),
            "txbuf_received": bool(s.mon_txbuf),
        }

        passed = all(required.values())
        snapshot = {
            "profile_policy": "TIME_REQUIRED_OTHER_DATA_OPTIONAL",
            "required": required,
            "optional": optional,
            "state": s.to_dict(),
            "captured_at_utc": utc_now_iso(),
        }
        return passed, snapshot

    def _provision_current_module(self) -> None:
        if not self._ensure_connected():
            return
        if not db_status(DEFAULT_DB).get("exists"):
            messagebox.showwarning(
                "GPS Lab Registry",
                "The physical SQLite database does not exist. Create it first.",
            )
            return
        if self.diag.state.rinv_is_default_empty is not True:
            messagebox.showwarning(
                "GPS Lab Registry",
                "Provisioning is allowed only when CFG-RINV is confirmed EMPTY / FACTORY DEFAULT.",
            )
            return

        passed, snapshot = self._current_test_snapshot()
        if not passed:
            messagebox.showwarning(
                "GPS Lab Registry",
                "Required quick test is not complete: GNSS/NMEA time has not been received yet.",
            )
            return

        tested_at = utc_now_iso()
        from .registry import build_rinv_text
        module_code = preview_next_module_code(tested_at, DEFAULT_DB)
        rinv_text = build_rinv_text(module_code, tested_at)

        if not messagebox.askyesno(
            "GPS Lab Provisioning",
            "Write this open technological marker to the receiver?\n\n"
            f"{rinv_text}\n\n"
            "It will later be saved to EEPROM. This is not a certificate or security identifier.",
        ):
            return

        row = add_inspection(
            payload=snapshot,
            board="GY-GPS6MV2",
            receiver=self.diag.state.receiver_identity or "u-blox 6",
            sw_version=self.diag.state.ubx_sw_version,
            hw_version=self.diag.state.ubx_hw_version,
            result="PENDING",
            tested_at_utc=tested_at,
            rinv_before=self.diag.state.rinv_text or "EMPTY / FACTORY DEFAULT",
            rinv_after=rinv_text,
            db_path=DEFAULT_DB,
        )
        if row["module_code"] != module_code:
            messagebox.showerror("GPS Lab Registry", "Module number allocation changed unexpectedly.")
            return

        self.registry_state_var.set("WRITING RINV TO RAM")
        self.registry_next_var.set(module_code)
        self.registry_rinv_var.set(rinv_text)
        self.worker.send(build_cfg_rinv_write(rinv_text.encode("ascii"), binary=False))
        self.after(400, lambda: self.worker.send(CFG_RINV_POLL))
        self.after(1200, lambda: self._finish_rinv_write(module_code, rinv_text, snapshot))

    def _finish_rinv_write(self, module_code: str, rinv_text: str, snapshot: dict) -> None:
        if self.diag.state.rinv_text != rinv_text:
            self.registry_state_var.set("RINV READ-BACK FAILED")
            self.registry_last_var.set(
                f"Expected {rinv_text!r}, got {self.diag.state.rinv_text!r}"
            )
            update_inspection(
                module_code,
                result="WRITE_VERIFY_FAILED",
                payload=snapshot | {"write_readback": False},
                db_path=DEFAULT_DB,
            )
            return

        self.registry_state_var.set("RINV READ-BACK PASS | SAVING TO EEPROM")
        self.worker.send(build_cfg_cfg_save_rinv())
        snapshot = snapshot | {
            "write_readback": True,
            "rinv_written": rinv_text,
            "eeprom_save_sent_at_utc": utc_now_iso(),
        }
        update_inspection(
            module_code,
            result="PENDING_POWER_CYCLE",
            rinv_after=rinv_text,
            payload=snapshot,
            db_path=DEFAULT_DB,
        )
        self.registry_last_var.set(
            "RINV RAM verify PASS; EEPROM save command sent. Power-cycle the module, reconnect, then Verify after power cycle."
        )
        self._refresh_registry_status()

    def _verify_persisted_module(self) -> None:
        if not self._ensure_connected():
            return
        self.worker.send(CFG_RINV_POLL)
        self.registry_state_var.set("READING RINV FOR PERSISTENCE VERIFY")
        self.after(700, self._finish_persistence_verify)

    def _finish_persistence_verify(self) -> None:
        if not self.diag.state.utc_time:
            self.registry_state_var.set("WAITING FOR GNSS TIME")
            self.registry_last_var.set(
                "RINV verification deferred: wait until GNSS/NMEA time is received, then press Verify after power cycle again."
            )
            return

        rinv_text = self.diag.state.rinv_text
        if not rinv_text:
            self.registry_state_var.set("VERIFY FAILED")
            self.registry_last_var.set("No readable CFG-RINV text.")
            return
        row = find_inspection_by_rinv(rinv_text, DEFAULT_DB)
        if row is None:
            self.registry_state_var.set("NOT IN LOCAL DATABASE")
            self.registry_last_var.set(f"RINV present but not found locally: {rinv_text}")
            return

        payload = row.get("payload", {})
        payload["power_cycle_verified"] = True
        payload["power_cycle_verified_at_utc"] = utc_now_iso()
        payload["verification_time_received"] = self.diag.state.utc_time
        payload["verification_date_received"] = self.diag.state.utc_date
        payload["verification_optional_state"] = self.diag.state.to_dict()
        update_inspection(
            row["module_code"],
            result="PASS",
            rinv_after=rinv_text,
            payload=payload,
            db_path=DEFAULT_DB,
        )
        self.registry_state_var.set("PASS | EEPROM PERSISTENCE VERIFIED")
        self.registry_last_var.set(
            f"{row['module_code']} verified after power cycle and recorded PASS."
        )
        self._refresh_registry_status()

    def _poll_engineering_all(self) -> None:
        if not self._ensure_connected():
            return
        for packet in (MON_HW_POLL, MON_IO_POLL, MON_RXBUF_POLL, MON_TXBUF_POLL):
            self.worker.send(packet)

    def _refresh_engineering(self) -> None:
        s = self.diag.state

        hw = s.mon_hw or {}
        if hw:
            self.eng_hw_vars["Payload bytes"].set(str(hw.get("payload_length", "-")))
            self.eng_hw_vars["Noise / ms"].set(str(hw.get("noise_per_ms", "-")))
            self.eng_hw_vars["AGC count"].set(str(hw.get("agc_cnt", "-")))
            self.eng_hw_vars["Antenna status"].set(str(hw.get("antenna_status", "-")))
            self.eng_hw_vars["Antenna power"].set(str(hw.get("antenna_power", "-")))
            jam_ind = hw.get("jam_ind")
            self.eng_hw_vars["Jamming indicator"].set("-" if jam_ind is None else str(jam_ind))
            self.eng_hw_vars["Jamming state"].set(str(hw.get("jamming_state_name", "-")))
            self.eng_hw_vars["RTC calibrated"].set(str(hw.get("rtc_calib", "-")))
            self.eng_hw_vars["Safe boot"].set(str(hw.get("safe_boot", "-")))

        for item in self.eng_io_tree.get_children():
            self.eng_io_tree.delete(item)
        for row in s.mon_io:
            self.eng_io_tree.insert(
                "",
                "end",
                values=(
                    row.get("name", row.get("port", "-")),
                    row.get("rx_bytes", "-"),
                    row.get("tx_bytes", "-"),
                    row.get("parity_errs", "-"),
                    row.get("framing_errs", "-"),
                    row.get("overrun_errs", "-"),
                    row.get("rx_busy", "-"),
                    row.get("tx_busy", "-"),
                ),
            )

        for tree, rows in (
            (self.eng_rx_tree, s.mon_rxbuf),
            (self.eng_tx_tree, (s.mon_txbuf or {}).get("targets", [])),
        ):
            for item in tree.get_children():
                tree.delete(item)
            for row in rows:
                tree.insert(
                    "",
                    "end",
                    values=(
                        row.get("name", row.get("target", "-")),
                        row.get("pending", "-"),
                        row.get("usage", "-"),
                        row.get("peak_usage", "-"),
                    ),
                )

        tx = s.mon_txbuf or {}
        if tx:
            self.eng_tx_status_var.set(
                "TX buffer status: total="
                f"{tx.get('total_usage', '-')}% "
                f"peak={tx.get('total_peak_usage', '-')}% | "
                f"limit={tx.get('limit_reached', '-')} "
                f"mem_err={tx.get('memory_allocation_error', '-')} "
                f"alloc_err={tx.get('allocation_error', '-')}"
            )

    def send_terminal_packet(self) -> None:
        if not self._ensure_connected():
            return

        text = self.ubx_hex_var.get().strip().replace(" ", "")
        if text.lower().startswith("0x"):
            text = text[2:]

        try:
            packet = bytes.fromhex(text)
        except ValueError:
            messagebox.showerror("UBX Terminal", "Invalid hexadecimal string.")
            return

        if not packet_is_valid(packet):
            messagebox.showerror(
                "UBX Terminal",
                "Packet rejected: use a complete UBX packet with a valid checksum.",
            )
            return

        self.worker.send(packet)

    def auto_probe(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("GPS Lab", "Disconnect before Auto Probe.")
            return

        port = self.port_var.get().strip()
        if not port:
            messagebox.showwarning("GPS Lab", "Select a serial port.")
            return

        self.connection_var.set(f"PROBING {port}...")
        self.auto_probe_thread = threading.Thread(
            target=self._auto_probe_worker,
            args=(port,),
            daemon=True,
        )
        self.auto_probe_thread.start()

    def _auto_probe_worker(self, port: str) -> None:
        try:
            diag = probe_port(port)
            self.events.put(("probe_result", diag))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def toggle_capture(self) -> None:
        if self.capture_file is not None:
            self._stop_capture()
            return

        if not self._ensure_connected():
            return

        path = filedialog.asksaveasfilename(
            title="Save raw GPS capture",
            defaultextension=".bin",
            filetypes=[
                ("Binary capture", "*.bin"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        try:
            self.capture_file = open(path, "wb")
        except OSError as exc:
            messagebox.showerror("GPS Lab", str(exc))
            return

        self.capture_button.configure(text="Stop Capture")

    def _stop_capture(self) -> None:
        if self.capture_file is not None:
            try:
                self.capture_file.close()
            finally:
                self.capture_file = None
        self.capture_button.configure(text="Start Capture")

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()

                if kind == "connected":
                    self.connection_var.set(
                        f"CONNECTED: {self.diag.state.port} @ "
                        f"{self.diag.state.baud}"
                    )
                    # u-blox 6 can be busy streaming NMEA at 9600 baud.
                    # Ask MON-VER by itself first and retry briefly instead of
                    # flooding the port with several UBX polls at once.
                    self.mon_ver_status_var.set("AUTO REQUEST")
                    self.after(80, lambda: self._request_mon_ver_retry(0))
                elif kind == "disconnected":
                    self.connection_var.set("DISCONNECTED")
                elif kind == "error":
                    self.connection_var.set("ERROR")
                    messagebox.showerror("GPS Lab", payload)
                    self.disconnect()
                elif kind == "data":
                    self._handle_data(payload)
                elif kind == "tx":
                    self._append_ubx("TX", payload)
                elif kind == "probe_result":
                    self._handle_probe_result(payload)
        except queue.Empty:
            pass

        self.after(100, self._poll_events)

    def _handle_probe_result(self, diag: GPSDiagnostics) -> None:
        self.diag = diag
        state = diag.state
        if state.baud:
            self.baud_var.set(str(state.baud))
        self._refresh_status()
        self.connection_var.set(
            f"PROBE COMPLETE: {state.protocol} @ {state.baud or '?'}"
        )

    def _handle_data(self, data: bytes) -> None:
        if self.capture_file is not None:
            try:
                self.capture_file.write(data)
                self.capture_file.flush()
            except OSError as exc:
                self._stop_capture()
                messagebox.showerror("GPS Lab Capture", str(exc))

        before = self.diag.state.ubx_frames
        self.diag.feed(data)
        if self.diag.state.ubx_frames > before:
            self._append_ubx("RX", data)
        self._append_raw(data)
        self._refresh_nmea_views()
        self._refresh_engineering()
        self._refresh_status()

    def _append_ubx(self, direction: str, data: bytes) -> None:
        line = f"{direction} {data.hex(' ').upper()}\n"
        self.ubx_text.configure(state="normal")
        self.ubx_text.insert("end", line)
        self.ubx_text.see("end")
        self.ubx_text.configure(state="disabled")

    def _clear_raw_stream(self) -> None:
        """Clear only the visible Raw Stream log; keep diagnostics and capture running."""
        self.raw_text.configure(state="normal")
        self.raw_text.delete("1.0", "end")
        self.raw_text.configure(state="disabled")

    def _append_raw(self, data: bytes) -> None:
        text = data.decode("ascii", "replace")
        self.raw_text.configure(state="normal")
        self.raw_text.insert("end", text)

        line_count = int(self.raw_text.index("end-1c").split(".")[0])
        if line_count > 3000:
            self.raw_text.delete("1.0", "1000.0")

        self.raw_text.see("end")
        self.raw_text.configure(state="disabled")


    def _refresh_nmea_views(self) -> None:
        latest = self.diag.state.latest_nmea_raw

        for message_type, view in self.nmea_views.items():
            raw = latest.get(message_type)
            if not raw:
                continue

            sentence = parse_sentence(raw)
            if sentence is None:
                continue

            info = explain_sentence(sentence)
            view["summary"].set(info["summary"])
            view["raw"].set(raw)
            count = self.diag.state.sentence_counts.get(message_type, 0)
            view["status"].set(
                f"Sentence: {info['sentence_id']} | Checksum: {info['checksum']} | Count: {count}"
            )

            tree = view["tree"]
            for item in tree.get_children():
                tree.delete(item)

            for row in info["rows"]:
                tree.insert(
                    "",
                    "end",
                    values=(
                        row["field"],
                        row["raw"],
                        row["decoded"],
                        row["meaning"],
                    ),
                )

    @staticmethod
    def _format_nmea_time(value: str | None) -> str:
        if not value or len(value) < 6:
            return "-"
        try:
            int(value[0:2])
            int(value[2:4])
            float(value[4:])
        except ValueError:
            return value
        return f"{value[0:2]}:{value[2:4]}:{value[4:]}"

    @staticmethod
    def _format_nmea_date(value: str | None) -> str:
        if not value or len(value) != 6:
            return "-"
        try:
            day = int(value[0:2])
            month = int(value[2:4])
            year2 = int(value[4:6])
        except ValueError:
            return value
        year = 2000 + year2 if year2 < 80 else 1900 + year2
        return f"{day:02d}.{month:02d}.{year:04d}"

    def _refresh_status(self) -> None:
        s = self.diag.state

        def value(v, suffix=""):
            return "-" if v is None else f"{v}{suffix}"

        self.protocol_var.set(s.protocol)
        self.receiver_var.set(value(s.receiver_identity))
        self.sw_var.set(value(s.ubx_sw_version))
        self.hw_var.set(value(s.ubx_hw_version))
        if s.ubx_sw_version or s.ubx_hw_version:
            self.mon_ver_status_var.set("RECEIVED")
        self.protver_var.set(value(s.protocol_version))
        self.serial_var.set(value(s.usb_serial_number))
        self.unique_var.set(value(s.unique_id))
        if s.rinv_flags is None:
            if self.rinv_status_var.get() != "READING...":
                self.rinv_status_var.set("NOT READ")
            self.rinv_text_var.set("-")
            self.rinv_hex_var.set("-")
        else:
            if s.rinv_is_default_empty is True:
                self.rinv_status_var.set("EMPTY / FACTORY DEFAULT")
            elif s.rinv_data:
                self.rinv_status_var.set("DATA PRESENT")
            else:
                self.rinv_status_var.set("READ / NO DATA")
            self.rinv_text_var.set(s.rinv_text or "-")
            self.rinv_hex_var.set(s.rinv_hex or "-")
        self.fix_var.set(s.fix)
        self.sats_used_var.set(value(s.satellites_used))
        self.sats_visible_var.set(value(s.satellites_visible))
        self.hdop_var.set(value(s.hdop))
        self.lat_var.set(value(s.latitude))
        self.lon_var.set(value(s.longitude))
        self.alt_var.set(value(s.altitude_m, " m"))
        gnss_time = self._format_nmea_time(s.utc_time)
        gnss_date = self._format_nmea_date(s.utc_date)
        self.gnss_time_var.set(gnss_time)
        self.gnss_date_var.set(gnss_date)

        if s.utc_time:
            if s.utc_date:
                self.utc_var.set(f"{gnss_date} {gnss_time} UTC")
                self.time_primary_var.set(
                    f"GNSS UTC: {gnss_time}   DATE: {gnss_date}"
                )
            else:
                self.utc_var.set(f"{gnss_time} UTC")
                self.time_primary_var.set(f"GNSS UTC: {gnss_time}")
        else:
            self.utc_var.set("-")
            self.time_primary_var.set("GNSS UTC: waiting...")

        now_utc = datetime.now(timezone.utc)
        self.system_utc_var.set(now_utc.strftime("%d.%m.%Y %H:%M:%S UTC"))

        if (
            s.ubx_utc_year is not None
            and s.ubx_utc_month is not None
            and s.ubx_utc_day is not None
            and s.ubx_utc_hour is not None
            and s.ubx_utc_minute is not None
            and s.ubx_utc_second is not None
        ):
            self.ubx_time_var.set(
                f"{s.ubx_utc_day:02d}.{s.ubx_utc_month:02d}.{s.ubx_utc_year:04d} "
                f"{s.ubx_utc_hour:02d}:{s.ubx_utc_minute:02d}:{s.ubx_utc_second:02d} UTC"
            )
        else:
            self.ubx_time_var.set("-")

        if s.ubx_utc_valid is True:
            self.ubx_time_valid_var.set("VALID UTC")
        elif s.ubx_utc_valid is False:
            self.ubx_time_valid_var.set("INVALID / NOT CONFIRMED")
        else:
            self.ubx_time_valid_var.set("NOT CHECKED")

        delta = utc_delta_seconds(s.utc_date, s.utc_time, now_utc)
        if delta is None:
            self.host_utc_delta_var.set("-")
        else:
            self.host_utc_delta_var.set(f"{delta:+.1f} s")

        if not s.utc_time:
            self.time_status_var.set("WAITING")
        elif s.ubx_utc_valid is True:
            if delta is not None and abs(delta) <= 10.0:
                self.time_status_var.set("TIME RECEIVED | UBX VALID | HOST MATCH")
            elif delta is not None:
                self.time_status_var.set("TIME RECEIVED | UBX VALID | HOST DIFFERENCE")
            else:
                self.time_status_var.set("TIME RECEIVED | UBX VALID")
        else:
            self.time_status_var.set("TIME RECEIVED")

        self.rate_var.set(
            "-" if s.gga_rate_hz is None else f"{s.gga_rate_hz:.2f} Hz"
        )
        self.bytes_var.set(str(s.bytes_received))

        if not s.has_data:
            status = "NO DATA"
        elif not s.has_protocol:
            status = "DATA / UNKNOWN PROTOCOL"
        elif s.utc_time and s.fix == "NO FIX":
            if s.ubx_utc_valid is True:
                status = "RECEIVER ALIVE | TIME RECEIVED | UBX VALID | NO FIX"
            else:
                status = "RECEIVER ALIVE | TIME RECEIVED | NO FIX"
        elif s.fix == "NO FIX":
            status = "RECEIVER ALIVE | NO FIX"
        else:
            status = f"RECEIVER ALIVE | {s.fix}"
        self.status_var.set(status)

    def destroy(self) -> None:
        self.disconnect()
        super().destroy()


def main() -> int:
    app = GPSGui()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
