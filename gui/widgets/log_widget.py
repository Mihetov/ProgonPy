import tkinter as tk
from tkinter import ttk


class LogWidget(ttk.LabelFrame):
    def __init__(self, parent):
        super().__init__(parent, text="LOG")

        self.text = tk.Text(self, height=20)
        self.text.pack(fill="both", expand=True)

    def append(self, msg):
        self.text.insert("end", msg + "\n")
        self.text.see("end")