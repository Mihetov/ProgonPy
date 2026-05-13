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
        self.root.title("Modbus Progon · Premium UI")
        self.root.geometry("1100x680")
        self.root.minsize(980, 620)

        self.poller = Poller(client, on_data=self.on_data)

        self._setup_style()
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_style(self):
        bg = "#111827"
        panel = "#1f2937"
        panel_2 = "#243244"
        text = "#e5e7eb"
        muted = "#9ca3af"
        accent = "#3b82f6"

        self.root.configure(bg=bg)

        style = ttk.Style()
        style.theme_use("clam")

        style.configure("App.TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel)

        style.configure("App.TLabel", background=panel, foreground=text, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=panel, foreground=muted, font=("Segoe UI", 9))

        style.configure(
            "Card.TLabelframe",
            background=panel,
            borderwidth=1,
            relief="solid",
            bordercolor=panel_2,
            padding=12,
        )
        style.configure("Card.TLabelframe.Label", background=panel, foreground=text, font=("Segoe UI Semibold", 10))

        style.configure("App.TButton", font=("Segoe UI", 10), padding=(10, 7), borderwidth=0)
        style.map("App.TButton", background=[("!disabled", accent), ("active", "#2563eb")], foreground=[("!disabled", "white")])

        style.configure("Secondary.TButton", font=("Segoe UI", 10), padding=(10, 7), background=panel_2, foreground=text)
        style.map("Secondary.TButton", background=[("active", "#31475f")])

        style.configure("App.TEntry", fieldbackground="#0f172a", foreground=text, insertcolor=text)
        style.configure("App.TCombobox", fieldbackground="#0f172a", foreground=text)

    def _build(self):
        root_wrap = ttk.Frame(self.root, style="App.TFrame")
        root_wrap.pack(fill="both", expand=True, padx=16, pady=16)

        left = ttk.Frame(root_wrap, style="App.TFrame")
        right = ttk.Frame(root_wrap, style="App.TFrame")

        left.pack(side="left", fill="y")
        right.pack(side="right", fill="both", expand=True, padx=(16, 0))

        header = ttk.Label(left, text="Connection & Polling", style="Muted.TLabel")
        header.pack(anchor="w", pady=(0, 8))

        self.transport = TransportWidget(left, self.client, on_log=self.append_log)
        self.transport.pack(fill="x", pady=(0, 12))

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
