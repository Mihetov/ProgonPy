import tkinter as tk
from tkinter import ttk


def parse_int(value):
    value = value.strip()
    return int(value, 0)


class ModbusWidgetRead(ttk.LabelFrame):
    def __init__(self, parent, client, poller):
        super().__init__(parent, text="MODBUS READ")

        self.client = client
        self.poller = poller

        self.slave = tk.StringVar(value="1")
        self.addr = tk.StringVar(value="0")
        self.count = tk.StringVar(value="10")
        self.interval = tk.StringVar(value="500")

        self._build()

    def _build(self):
        ttk.Label(self, text="Slave").pack(anchor="w")
        ttk.Entry(self, textvariable=self.slave).pack(fill="x")

        ttk.Label(self, text="Start Address (dec or hex 0x...)").pack(anchor="w")
        ttk.Entry(self, textvariable=self.addr).pack(fill="x")

        ttk.Label(self, text="Count").pack(anchor="w")
        ttk.Entry(self, textvariable=self.count).pack(fill="x")

        ttk.Label(self, text="Interval ms").pack(anchor="w")
        ttk.Entry(self, textvariable=self.interval).pack(fill="x")

        ttk.Button(self, text="START LIVE", command=self.start).pack(fill="x", pady=2)
        ttk.Button(self, text="STOP", command=self.stop).pack(fill="x", pady=2)

    def start(self):
        self.poller.configure(
            parse_int(self.slave.get()),
            parse_int(self.addr.get()),
            parse_int(self.count.get()),
            int(self.interval.get()) / 1000
        )
        self.poller.start()

    def stop(self):
        self.poller.stop()

    