from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .diagnostics import GPSDiagnostics
from .nmea import explain_sentence, parse_sentence
from .serialio import DEFAULT_BAUD_RATES, list_serial_ports, open_serial, probe_port
from .timecheck import utc_delta_seconds
from .ubx import (
    CFG_USB_POLL,
    MON_VER_POLL,
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
        self.title("GPS Lab Diagnostic Console v0.3")
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
        self.protver_var = tk.StringVar(value="-")
        self.serial_var = tk.StringVar(value="-")
        self.unique_var = tk.StringVar(value="-")
        self.fix_var = tk.StringVar(value="NO FIX")
        self.sats_used_var = tk.StringVar(value="-")
        self.sats_visible_var = tk.StringVar(value="-")
        self.hdop_var = tk.StringVar(value="-")
        self.lat_var = tk.StringVar(value="-")
        self.lon_var = tk.StringVar(value="-")
        self.alt_var = tk.StringVar(value="-")
        self.utc_var = tk.StringVar(value="-")
        self.host_utc_delta_var = tk.StringVar(value="-")
        self.time_status_var = tk.StringVar(value="WAITING")
        self.rate_var = tk.StringVar(value="-")
        self.bytes_var = tk.StringVar(value="0")
        self.ubx_hex_var = tk.StringVar()

        self._build_ui()
        self.refresh_ports()
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

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        overview = ttk.Frame(notebook, padding=12)
        identity = ttk.Frame(notebook, padding=12)
        ubx_terminal = ttk.Frame(notebook, padding=8)
        nmea = ttk.Frame(notebook, padding=6)
        raw = ttk.Frame(notebook, padding=6)

        notebook.add(overview, text="Overview")
        notebook.add(identity, text="Identity / Time")
        notebook.add(nmea, text="NMEA Decoder")
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
            ("UTC", self.utc_var),
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

        identity_fields = [
            ("Receiver", self.receiver_var),
            ("SW version", self.sw_var),
            ("HW version", self.hw_var),
            ("Protocol version", self.protver_var),
            ("USB serial", self.serial_var),
            ("Unique ID", self.unique_var),
            ("UTC", self.utc_var),
            ("Host UTC delta", self.host_utc_delta_var),
            ("Time status", self.time_status_var),
        ]

        for row, (label, var) in enumerate(identity_fields):
            ttk.Label(identity, text=label + ":").grid(
                row=row, column=0, sticky="w", padx=(0, 16), pady=3
            )
            ttk.Label(
                identity,
                textvariable=var,
                font=("TkDefaultFont", 10, "bold"),
            ).grid(row=row, column=1, sticky="w", pady=3)

        ttk.Button(identity, text="Poll MON-VER", command=lambda: self._send_named(MON_VER_POLL)).grid(
            row=10, column=0, sticky="w", pady=(12, 2)
        )
        ttk.Button(identity, text="Poll CFG-USB", command=lambda: self._send_named(CFG_USB_POLL)).grid(
            row=10, column=1, sticky="w", padx=(8, 0), pady=(12, 2)
        )
        ttk.Button(identity, text="Poll SEC-UNIQID", command=lambda: self._send_named(SEC_UNIQID_POLL)).grid(
            row=11, column=0, sticky="w", pady=2
        )

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

        self.raw_text = tk.Text(
            raw, wrap="none", font=("Consolas", 9), state="disabled"
        )
        ybar = ttk.Scrollbar(raw, orient="vertical", command=self.raw_text.yview)
        xbar = ttk.Scrollbar(raw, orient="horizontal", command=self.raw_text.xview)
        self.raw_text.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.raw_text.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        raw.rowconfigure(0, weight=1)
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

    def identify_all(self) -> None:
        if not self._ensure_connected():
            return
        for packet in (MON_VER_POLL, CFG_USB_POLL, SEC_UNIQID_POLL):
            self.worker.send(packet)
        self.connection_var.set(
            self.connection_var.get() + " | identity polls sent"
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
        self._refresh_status()

    def _append_ubx(self, direction: str, data: bytes) -> None:
        line = f"{direction} {data.hex(' ').upper()}\n"
        self.ubx_text.configure(state="normal")
        self.ubx_text.insert("end", line)
        self.ubx_text.see("end")
        self.ubx_text.configure(state="disabled")

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

    def _refresh_status(self) -> None:
        s = self.diag.state

        def value(v, suffix=""):
            return "-" if v is None else f"{v}{suffix}"

        self.protocol_var.set(s.protocol)
        self.receiver_var.set(value(s.receiver_identity))
        self.sw_var.set(value(s.ubx_sw_version))
        self.hw_var.set(value(s.ubx_hw_version))
        self.protver_var.set(value(s.protocol_version))
        self.serial_var.set(value(s.usb_serial_number))
        self.unique_var.set(value(s.unique_id))
        self.fix_var.set(s.fix)
        self.sats_used_var.set(value(s.satellites_used))
        self.sats_visible_var.set(value(s.satellites_visible))
        self.hdop_var.set(value(s.hdop))
        self.lat_var.set(value(s.latitude))
        self.lon_var.set(value(s.longitude))
        self.alt_var.set(value(s.altitude_m, " m"))
        self.utc_var.set(
            " ".join(x for x in (s.utc_date, s.utc_time) if x) or "-"
        )

        delta = utc_delta_seconds(s.utc_date, s.utc_time)
        if delta is None:
            self.host_utc_delta_var.set("-")
            self.time_status_var.set("WAITING")
        else:
            self.host_utc_delta_var.set(f"{delta:+.1f} s")
            if (s.satellites_visible or 0) > 0 and abs(delta) <= 10.0:
                self.time_status_var.set("TIME PASS")
            else:
                self.time_status_var.set("TIME PRESENT")

        self.rate_var.set(
            "-" if s.gga_rate_hz is None else f"{s.gga_rate_hz:.2f} Hz"
        )
        self.bytes_var.set(str(s.bytes_received))

        if not s.has_data:
            status = "NO DATA"
        elif not s.has_protocol:
            status = "DATA / UNKNOWN PROTOCOL"
        elif self.time_status_var.get() == "TIME PASS" and s.fix == "NO FIX":
            status = "RECEIVER ALIVE | TIME VALID | NO FIX"
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
