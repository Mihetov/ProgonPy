from gui.state.poller import Poller
from gui.widgets.modbus_widget_read import ModbusWidgetRead
from gui.widgets.transport_widget import TransportWidget
from gui.widgets.log_widget import LogWidget

import tkinter as tk
from tkinter import ttk


class MainWindow:
    def __init__(self, client, logger=None):
        self.client = client
        self.logger = logger

        self.root = tk.Tk()
        self.root.title("Modbus progon")
        self.root.geometry("1000x600")

        self.poller = Poller(client, on_data=self.on_data)

        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self):
        left = ttk.Frame(self.root)
        right = ttk.Frame(self.root)

        left.pack(side="left", fill="y")
        right.pack(side="right", fill="both", expand=True)

        self.transport = TransportWidget(left, self.client, on_log=self.append_log)
        self.transport.pack(fill="x")

        self.modbus = ModbusWidgetRead(left, self.client, self.poller)
        self.modbus.pack(fill="x")

        self.log_widget = LogWidget(right)
        self.log_widget.pack(fill="both", expand=True)

    def append_log(self, message):
        self.root.after(0, lambda: self.log_widget.append(str(message)))

    def on_data(self, data):
        self.append_log(data)

    def _on_close(self):
        self.poller.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
