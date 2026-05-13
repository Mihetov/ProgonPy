import tkinter as tk
from tkinter import ttk, messagebox


def parse_int(value):
    value = value.strip()
    return int(value, 0)


class ModbusWidgetRead(ttk.LabelFrame):
    def __init__(self, parent, client, poller):
        super().__init__(parent, text="Modbus Read", style="Card.TLabelframe")

        self.client = client
        self.poller = poller

        self.slave = tk.StringVar(value="1")
        self.addr = tk.StringVar(value="0")
        self.count = tk.StringVar(value="10")
        self.interval = tk.StringVar(value="500")

        self._build()

    def _build(self):
        body = ttk.Frame(self, style="Panel.TFrame")
        body.pack(fill="x")

        ttk.Label(body, text="Slave ID", style="App.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(body, textvariable=self.slave, style="App.TEntry").grid(row=1, column=0, sticky="ew", padx=(0, 8))

        ttk.Label(body, text="Start Address", style="App.TLabel").grid(row=0, column=1, sticky="w", pady=(0, 4))
        ttk.Entry(body, textvariable=self.addr, style="App.TEntry").grid(row=1, column=1, sticky="ew")

        ttk.Label(body, text="Count", style="App.TLabel").grid(row=2, column=0, sticky="w", pady=(10, 4))
        ttk.Entry(body, textvariable=self.count, style="App.TEntry").grid(row=3, column=0, sticky="ew", padx=(0, 8))

        ttk.Label(body, text="Interval (ms)", style="App.TLabel").grid(row=2, column=1, sticky="w", pady=(10, 4))
        ttk.Entry(body, textvariable=self.interval, style="App.TEntry").grid(row=3, column=1, sticky="ew")

        ttk.Button(body, text="Start Live", command=self.start, style="App.TButton").grid(row=4, column=0, columnspan=2, sticky="ew", pady=(14, 6))
        ttk.Button(body, text="Stop", command=self.stop, style="Secondary.TButton").grid(row=5, column=0, columnspan=2, sticky="ew")

        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

    def start(self):
        try:
            slave = parse_int(self.slave.get())
            addr = parse_int(self.addr.get())
            count = parse_int(self.count.get())
            interval = int(self.interval.get()) / 1000
        except ValueError:
            messagebox.showerror("Input Error", "Fields must contain valid numeric values")
            return

        if slave < 0 or addr < 0 or count <= 0 or interval <= 0:
            messagebox.showerror("Input Error", "slave/address must be >= 0, count/interval must be > 0")
            return

        self.poller.configure(slave, addr, count, interval)
        self.poller.start()

    def stop(self):
        self.poller.stop()
