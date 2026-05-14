import tkinter as tk
from tkinter import ttk, messagebox


BAUD_RATES = ["9600", "19200", "38400", "57600", "115200"]
PARITY_OPTIONS = ["none", "even", "odd"]
STOP_BITS_OPTIONS = ["1", "2"]


class TransportWidget(ttk.LabelFrame):
    IS_APP_WIDGET = True
    PANEL_TITLE = "1.Настройка COM-порта"

    def __init__(self, parent, client, poller=None, on_log=None):
        super().__init__(parent, text=self.PANEL_TITLE, style="Card.TLabelframe")

        self.client = client
        self.poller = poller
        self.on_log = on_log

        self.port = tk.StringVar(value="")
        self.baud = tk.StringVar(value="115200")
        self.parity = tk.StringVar(value="none")
        self.stop_bits = tk.StringVar(value="1")

        self._build()
        self.refresh_ports()

    def _build(self):
        body = ttk.Frame(self, style="Panel.TFrame")
        body.pack(fill="x")

        ttk.Label(body, text="COM Port", style="App.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.port_combo = ttk.Combobox(body, textvariable=self.port, state="readonly", style="App.TCombobox")
        self.port_combo.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(body, text="Refresh", command=self.refresh_ports, style="Secondary.TButton").grid(row=1, column=1, sticky="ew")

        ttk.Label(body, text="Baudrate", style="App.TLabel").grid(row=2, column=0, sticky="w", pady=(10, 4))
        ttk.Combobox(body, textvariable=self.baud, values=BAUD_RATES, state="readonly", style="App.TCombobox").grid(row=3, column=0, columnspan=2, sticky="ew")

        ttk.Label(body, text="Parity", style="App.TLabel").grid(row=4, column=0, sticky="w", pady=(10, 4))
        ttk.Combobox(body, textvariable=self.parity, values=PARITY_OPTIONS, state="readonly", style="App.TCombobox").grid(row=5, column=0, sticky="ew", padx=(0, 8))

        ttk.Label(body, text="Stop Bits", style="App.TLabel").grid(row=4, column=1, sticky="w", pady=(10, 4))
        ttk.Combobox(body, textvariable=self.stop_bits, values=STOP_BITS_OPTIONS, state="readonly", style="App.TCombobox").grid(row=5, column=1, sticky="ew")

        ttk.Button(body, text="Connect", command=self.open_rtu, style="App.TButton").grid(row=6, column=0, columnspan=2, sticky="ew", pady=(14, 6))
        ttk.Button(body, text="Disconnect", command=self.close, style="Secondary.TButton").grid(row=7, column=0, columnspan=2, sticky="ew")

        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

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
        ports = raw_ports.get("ports", []) if isinstance(raw_ports, dict) else raw_ports
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
            parity=self.parity.get().strip().lower(),
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
