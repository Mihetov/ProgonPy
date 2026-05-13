import tkinter as tk
from tkinter import ttk


class LogWidget(ttk.LabelFrame):
    def __init__(self, parent):
        super().__init__(parent, text="Live Log", style="Card.TLabelframe")

        wrap = ttk.Frame(self, style="Panel.TFrame")
        wrap.pack(fill="both", expand=True)

        self.text = tk.Text(
            wrap,
            height=20,
            bg="#0b1220",
            fg="#d1d5db",
            insertbackground="#d1d5db",
            relief="flat",
            font=("Consolas", 10),
            padx=10,
            pady=10,
        )
        self.text.pack(fill="both", expand=True)

    def append(self, msg):
        self.text.insert("end", msg + "\n")
        self.text.see("end")
