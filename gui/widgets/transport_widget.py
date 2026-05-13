import tkinter as tk
from tkinter import ttk


class TransportWidget(ttk.LabelFrame):
    def __init__(self, parent, client):
        super().__init__(parent, text="TRANSPORT")

        self.client = client

        self.port = tk.StringVar(value="COM19")
        self.baud = tk.StringVar(value="115200")

        ttk.Label(self, text="COM Port").pack(anchor="w")
        ttk.Entry(self, textvariable=self.port).pack(fill="x")

        ttk.Label(self, text="Baudrate").pack(anchor="w")
        ttk.Entry(self, textvariable=self.baud).pack(fill="x")

        ttk.Button(self, text="Open RTU", command=self.open_rtu).pack(fill="x", pady=2)
        ttk.Button(self, text="Close", command=self.close).pack(fill="x", pady=2)

    def open_rtu(self):
        self.client.open_rtu(
            self.port.get(),
            int(self.baud.get())
        )

    def close(self):
        self.client.close_transport()