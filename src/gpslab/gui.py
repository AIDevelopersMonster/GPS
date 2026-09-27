from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .diagnostics import GPSDiagnostics
from .serialio import DEFAULT_BAUD_RATES, list_serial_ports, open_serial, probe_port
from .ubx import MON_VER_POLL


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
        self.title("GPS Lab Diagnostic Console v0.1")
        self.geometry("980x700")
        self.minsize(820, 580)

        self.events: queue.Queue = queue.Queue()
        self.worker: SerialWorker | None = None
        self.diag = GPSDiagnostics()
        self.capture_file = None
        self.auto_probe_thread: threading.Thread | None = None

        self.port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value="9600")
        self.connection_var = tk.StringVar(value="DISCONNECTED")
        self.protocol_var = tk.StringVar(value="NONE")
        self.receiver_var = tk.StringVar(value="-")
        self.fix_var = tk.StringVar(value="NO FIX")
        self.sats_used_var = tk.StringVar(value="-")
        self.sats_visible_var = tk.StringVar(value="-")
        self.hdop_var = tk.StringVar(value="-")
        self.lat_var = tk.StringVar(value="-")
        self.lon_var = tk.StringVar(value="-")
        self.alt_var = tk.StringVar(value="-")
        self.utc_var = tk.StringVar(value="-")
        self.rate_var = tk.StringVar(value="-")
        self.bytes_var = tk.StringVar(value="0")

        self._build_ui()
        self.refresh_ports()
        self.after(100, self._poll_events)

    def _build_ui(self) -> None:
        controls = ttk.Frame(self, padding=8)
        controls.pack(fill="x")

        ttk.Label(controls, text="Port").grid(row=0, column=0, sticky="w")
        self.port_combo = ttk.Combobox(
            controls, textvariable=self.port_var, width=16, state="normal"
        )
        self.port_combo.grid(row=0, column=1, padx=(4, 10))

        ttk.Button(
            controls, text="Refresh", command=self.refresh_ports
        ).grid(row=0, column=2, padx=(0, 10))

        ttk.Label(controls, text="Baud").grid(row=0, column=3, sticky="w")
        self.baud_combo = ttk.Combobox(
            controls,
            textvariable=self.baud_var,
            values=[str(x) for x in DEFAULT_BAUD_RATES],
            width=10,
            state="normal",
        )
        self.baud_combo.grid(row=0, column=4, padx=(4, 10))

        ttk.Button(
            controls, text="Auto Probe", command=self.auto_probe
        ).grid(row=0, column=5, padx=4)

        self.connect_button = ttk.Button(
            controls, text="Connect", command=self.toggle_connection
        )
        self.connect_button.grid(row=0, column=6, padx=4)

        ttk.Button(
            controls, text="Identify UBX", command=self.identify_ubx
        ).grid(row=0, column=7, padx=4)

        self.capture_button = ttk.Button(
            controls, text="Start Capture", command=self.toggle_capture
        )
        self.capture_button.grid(row=0, column=8, padx=4)

        ttk.Label(
            controls,
            textvariable=self.connection_var,
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=1, column=0, columnspan=9, sticky="w", pady=(8, 0))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        overview = ttk.Frame(notebook, padding=12)
        raw = ttk.Frame(notebook, padding=6)
        notebook.add(overview, text="Overview")
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

        overview.columnconfigure(1, weight=1)

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

    def identify_ubx(self) -> None:
        if not self.worker or not self.worker.is_alive():
            messagebox.showinfo(
                "GPS Lab",
                "Connect to the receiver first.",
            )
            return
        self.worker.send(MON_VER_POLL)
        self.connection_var.set(
            self.connection_var.get() + " | UBX MON-VER poll sent"
        )

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

        if not self.worker or not self.worker.is_alive():
            messagebox.showinfo("GPS Lab", "Connect before starting capture.")
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

        self.diag.feed(data)
        self._append_raw(data)
        self._refresh_status()

    def _append_raw(self, data: bytes) -> None:
        text = data.decode("ascii", "replace")
        self.raw_text.configure(state="normal")
        self.raw_text.insert("end", text)

        line_count = int(self.raw_text.index("end-1c").split(".")[0])
        if line_count > 3000:
            self.raw_text.delete("1.0", "1000.0")

        self.raw_text.see("end")
        self.raw_text.configure(state="disabled")

    def _refresh_status(self) -> None:
        s = self.diag.state

        def value(v, suffix=""):
            return "-" if v is None else f"{v}{suffix}"

        self.protocol_var.set(s.protocol)
        self.receiver_var.set(value(s.receiver_identity))
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
        self.rate_var.set(
            "-" if s.gga_rate_hz is None else f"{s.gga_rate_hz:.2f} Hz"
        )
        self.bytes_var.set(str(s.bytes_received))

    def destroy(self) -> None:
        self.disconnect()
        super().destroy()


def main() -> int:
    app = GPSGui()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
