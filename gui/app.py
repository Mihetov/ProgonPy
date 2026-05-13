import importlib
import inspect
import pkgutil
from pathlib import Path

import tkinter as tk
from tkinter import ttk

from gui.state.poller import Poller


class MainWindow:
    def __init__(self, client, logger=None):
        self.client = client
        self.logger = logger

        self.root = tk.Tk()
        self.root.title("Modbus Progon · Modular UI")
        self.root.geometry("1180x700")
        self.root.minsize(1040, 620)

        self.poller = Poller(client, on_data=self.on_data)
        self.widget_factories = []
        self.active_widget = None
        self.nav_buttons = {}
        self.selected_widget_cls = None

        self._setup_style()
        self._build()
        self._load_widgets_from_folder()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_style(self):
        bg = "#18222d"
        side = "#121a24"
        panel = "#223041"
        panel_border = "#2f4258"
        text = "#eef3f8"
        muted = "#afbdcc"
        accent = "#4ea1ff"

        self.root.configure(bg=bg)

        style = ttk.Style()
        style.theme_use("clam")

        style.configure("App.TFrame", background=bg)
        style.configure("Sidebar.TFrame", background=side)
        style.configure("Panel.TFrame", background=panel)

        style.configure("App.TLabel", background=panel, foreground=text, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=side, foreground=muted, font=("Segoe UI", 11))
        style.configure("SidebarTitle.TLabel", background=side, foreground="#f2f6fb", font=("Segoe UI Semibold", 14))

        style.configure(
            "Card.TLabelframe",
            background=panel,
            borderwidth=1,
            relief="solid",
            bordercolor=panel_border,
            padding=12,
        )
        style.configure("Card.TLabelframe.Label", background=panel, foreground=text, font=("Segoe UI Semibold", 16))

        style.configure("App.TButton", font=("Segoe UI", 10), padding=(10, 7), borderwidth=0)
        style.map("App.TButton", background=[("!disabled", accent), ("active", "#3f8ddd")], foreground=[("!disabled", "#ffffff")])

        style.configure("Secondary.TButton", font=("Segoe UI", 10), padding=(10, 7), background="#314255", foreground=text)
        style.map("Secondary.TButton", background=[("active", "#3a4f67")])

        style.configure("App.TEntry", fieldbackground="#0f1721", foreground=text, insertcolor=text)
        style.configure("App.TCombobox", fieldbackground="#0f1721", foreground=text)
        style.map("App.TCombobox",
                  fieldbackground=[("readonly", "#0f1721")],
                  foreground=[("readonly", "#eef3f8")],
                  selectforeground=[("readonly", "#eef3f8")],
                  selectbackground=[("readonly", "#0f1721")])

        style.configure("Nav.TButton", background="#1f2b38", foreground=text, padding=(10, 10), anchor="w", relief="flat", font=("Segoe UI", 11))
        style.map("Nav.TButton", background=[("active", "#2a3a4d")], foreground=[("active", "#ffffff")])
        style.configure("NavSelected.TButton", background="#3f8ddd", foreground="#ffffff", padding=(10, 10), anchor="w", relief="flat", font=("Segoe UI Semibold", 11))
        style.map("NavSelected.TButton", background=[("active", "#3f8ddd")], foreground=[("active", "#ffffff")])

        self.root.option_add("*TCombobox*Listbox.background", "#0f1721")
        self.root.option_add("*TCombobox*Listbox.foreground", "#eef3f8")
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#314255")
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    def _build(self):
        root_wrap = ttk.Frame(self.root, style="App.TFrame")
        root_wrap.pack(fill="both", expand=True, padx=12, pady=12)

        self.left = ttk.Frame(root_wrap, style="Sidebar.TFrame", width=280)
        self.right = ttk.Frame(root_wrap, style="App.TFrame")

        self.left.pack(side="left", fill="y")
        self.right.pack(side="right", fill="both", expand=True, padx=(14, 0))
        self.left.pack_propagate(False)

        ttk.Label(self.left, text="Модули", style="SidebarTitle.TLabel").pack(anchor="w", padx=12, pady=(12, 4))
        ttk.Label(self.left, text="Выбери виджет слева", style="Muted.TLabel").pack(anchor="w", padx=12, pady=(0, 12))

        self.nav_container = ttk.Frame(self.left, style="Sidebar.TFrame")
        self.nav_container.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.content_host = ttk.Frame(self.right, style="App.TFrame")
        self.content_host.pack(fill="both", expand=True)

    def _discover_widget_classes(self):
        widgets_path = Path(__file__).resolve().parent / "widgets"
        module_prefix = "gui.widgets"
        discovered = []

        for module_info in pkgutil.iter_modules([str(widgets_path)]):
            if module_info.name.startswith("__"):
                continue

            module_name = f"{module_prefix}.{module_info.name}"
            module = importlib.import_module(module_name)

            for _, obj in inspect.getmembers(module, inspect.isclass):
                if obj.__module__ != module_name:
                    continue
                if not getattr(obj, "IS_APP_WIDGET", False):
                    continue
                discovered.append(obj)

        discovered.sort(key=lambda cls: getattr(cls, "PANEL_TITLE", cls.__name__).lower())
        return discovered

    def _load_widgets_from_folder(self):
        for w in self.nav_container.winfo_children():
            w.destroy()

        self.widget_factories = self._discover_widget_classes()

        if not self.widget_factories:
            ttk.Label(self.content_host, text="Нет доступных виджетов в gui/widgets", style="App.TLabel").pack(anchor="w", padx=12, pady=12)
            return

        self.nav_buttons = {}
        for widget_cls in self.widget_factories:
            title = getattr(widget_cls, "PANEL_TITLE", widget_cls.__name__)
            btn = ttk.Button(
                self.nav_container,
                text=title,
                style="Nav.TButton",
                command=lambda cls=widget_cls: self._show_widget(cls),
            )
            btn.pack(fill="x", pady=4)
            self.nav_buttons[widget_cls] = btn

        self._show_widget(self.widget_factories[0])

    def _show_widget(self, widget_cls):
        for child in self.content_host.winfo_children():
            child.destroy()

        self.selected_widget_cls = widget_cls
        for cls, btn in self.nav_buttons.items():
            btn.configure(style="NavSelected.TButton" if cls == widget_cls else "Nav.TButton")

        self.active_widget = widget_cls(
            self.content_host,
            self.client,
            self.poller,
            on_log=self.append_log,
        )
        self.active_widget.pack(fill="both", expand=True)

    def append_log(self, message):
        if self.logger:
            self.logger.info(str(message))

    def on_data(self, data):
        self.append_log(data)

    def _on_close(self):
        self.poller.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
