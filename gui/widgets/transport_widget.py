import tkinter as tk
from tkinter import ttk, messagebox


BAUD_RATES = ["9600", "19200", "38400", "57600", "115200"]
PARITY_OPTIONS = ["none", "even", "odd"]
STOP_BITS_OPTIONS = ["1", "2"]


class TransportWidget(ttk.LabelFrame):
    def __init__(self, parent, client, on_log=None):
        super().__init__(parent, text="TRANSPORT")

        self.client = client
        self.on_log = on_log

        self.port = tk.StringVar(value="")
        self.baud = tk.StringVar(value="115200")
        self.parity = tk.StringVar(value="none")
        self.stop_bits = tk.StringVar(value="1")

        self._build()
        self.refresh_ports()

    def _build(self):
        ttk.Label(self, text="COM Port").pack(anchor="w")
        self.port_combo = ttk.Combobox(self, textvariable=self.port, state="readonly")
        self.port_combo.pack(fill="x")

        ttk.Button(self, text="Refresh Ports", command=self.refresh_ports).pack(fill="x", pady=2)

        ttk.Label(self, text="Baudrate").pack(anchor="w")
        ttk.Combobox(self, textvariable=self.baud, values=BAUD_RATES, state="readonly").pack(fill="x")

        ttk.Label(self, text="Parity").pack(anchor="w")
        ttk.Combobox(self, textvariable=self.parity, values=PARITY_OPTIONS, state="readonly").pack(fill="x")

        ttk.Label(self, text="Stop Bits").pack(anchor="w")
        ttk.Combobox(self, textvariable=self.stop_bits, values=STOP_BITS_OPTIONS, state="readonly").pack(fill="x")

        ttk.Button(self, text="Connect", command=self.open_rtu).pack(fill="x", pady=2)
        ttk.Button(self, text="Disconnect", command=self.close).pack(fill="x", pady=2)

    def _notify(self, msg, is_error=False):
        if self.on_log:
            self.on_log(msg)
        if is_error:
            messagebox.showerror("Transport Error", msg)

    def refresh_ports(self):
        resp = self.client.serial_ports()

        if "error" in resp:
            self.port_combo["values"] = []
            self.port.set("")
            self._notify(f"Failed to load serial ports: {resp['error']}", is_error=True)
            return

        raw_ports = resp.get("result", [])
        if isinstance(raw_ports, dict):
            ports = raw_ports.get("ports", [])
        else:
            ports = raw_ports

        ports = [str(p) for p in ports]
        self.port_combo["values"] = ports

        if ports:
            self.port.set(ports[0])
            self._notify(f"Loaded {len(ports)} serial port(s)")
        else:
            self.port.set("")
            self._notify("No serial ports found")

    def open_rtu(self):
        if not self.port.get().strip():
            self._notify("Select a COM port before connecting", is_error=True)
            return

        try:
            baud = int(self.baud.get())
            stop_bits = int(self.stop_bits.get())
        except ValueError:
            self._notify("Baudrate/Stop bits must be valid numbers", is_error=True)
            return

        resp = self.client.open_rtu(
            self.port.get().strip(),
            baud=baud,
            stop_bits=stop_bits,
            parity=self.parity.get().strip().lower()
        )

        if "error" in resp:
            self._notify(f"Connect failed: {resp['error']}", is_error=True)
        else:
            self._notify("Transport connected")

    def close(self):
        resp = self.client.close_transport()
        if "error" in resp:
            self._notify(f"Disconnect failed: {resp['error']}", is_error=True)
        else:
            self._notify("Transport disconnected")
