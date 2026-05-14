import tkinter as tk
from tkinter import ttk, messagebox
import time


BAUD_RATES = ["9600", "19200", "38400", "57600", "115200"]
PARITY_OPTIONS = ["none", "even", "odd"]
STOP_BITS_OPTIONS = ["1", "2"]


class TransportWidget(ttk.LabelFrame):
    """Виджет настройки и управления транспортным соединением"""
    
    IS_APP_WIDGET = True
    PANEL_TITLE = "1. Настройка COM-порта"

    # Цвета статусов (text, bg)
    STATUS_COLORS = {
        "disconnected": ("#616161", "#2a2a2a"),
        "connecting": ("#FFA726", "#3e2723"),
        "connected": ("#66BB6A", "#1b5e20"),
        "error": ("#EF5350", "#b71c1c"),
    }

    def __init__(self, parent, client, poller=None, on_log=None):
        super().__init__(parent, text=self.PANEL_TITLE, style="Card.TLabelframe")

        self.client = client
        self.poller = poller
        self.on_log = on_log

        # Настройки подключения
        self.port = tk.StringVar(value="")
        self.baud = tk.StringVar(value="115200")
        self.parity = tk.StringVar(value="none")
        self.stop_bits = tk.StringVar(value="1")

        # Состояние
        self._connection_state = "disconnected"
        self._last_status_info = {}
        self._status_poll_active = False
        self._status_poll_interval = 2000

        self._build()
        self._update_ui_state()
        self.after(500, self.refresh_ports)
        self.after(1000, self._start_status_poll)

    # =========================================================
    # UI BUILD (Тёмная тема)
    # =========================================================

    def _build(self):
        body = ttk.Frame(self, style="Panel.TFrame")
        body.pack(fill="x", padx=8, pady=8)

        # ----------------- STATUS INDICATOR -----------------
        status_frame = ttk.Frame(body, style="Panel.TFrame")
        status_frame.pack(fill="x", pady=(0, 12))

        self.status_indicator = tk.Canvas(
            status_frame, width=20, height=20, highlightthickness=0, bg="#223041"
        )
        self.status_indicator.pack(side="left", padx=(0, 8))
        self._draw_status_indicator()

        self.status_label = ttk.Label(
            status_frame, text="Статус: Не подключено", style="App.TLabel"
        )
        self.status_label.pack(side="left")

        self.status_detail = ttk.Label(
            status_frame, text="", style="Muted.TLabel", font=("Segoe UI", 9)
        )
        self.status_detail.pack(side="right")

        # ----------------- PORT SETTINGS -----------------
        settings_frame = ttk.LabelFrame(body, text="Параметры подключения", style="Card.TLabelframe")
        settings_frame.pack(fill="x", pady=(0, 8))

        # COM Port
        port_row = ttk.Frame(settings_frame, style="Panel.TFrame")
        port_row.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(port_row, text="COM Port:", width=12, style="App.TLabel").pack(side="left")
        self.port_combo = ttk.Combobox(
            port_row, textvariable=self.port, state="readonly", style="App.TCombobox", width=15
        )
        self.port_combo.pack(side="left", padx=(4, 8))
        ttk.Button(
            port_row, text="🔄", width=3, command=self.refresh_ports, style="Secondary.TButton"
        ).pack(side="left")

        # Baudrate
        baud_row = ttk.Frame(settings_frame, style="Panel.TFrame")
        baud_row.pack(fill="x", padx=8, pady=4)
        ttk.Label(baud_row, text="Baudrate:", width=12, style="App.TLabel").pack(side="left")
        ttk.Combobox(
            baud_row, textvariable=self.baud, values=BAUD_RATES,
            state="readonly", style="App.TCombobox", width=15
        ).pack(side="left", padx=(4, 8))

        # Parity + Stop Bits
        parity_row = ttk.Frame(settings_frame, style="Panel.TFrame")
        parity_row.pack(fill="x", padx=8, pady=4)
        ttk.Label(parity_row, text="Parity:", width=12, style="App.TLabel").pack(side="left")
        ttk.Combobox(
            parity_row, textvariable=self.parity, values=PARITY_OPTIONS,
            state="readonly", style="App.TCombobox", width=10
        ).pack(side="left", padx=(4, 16))
        ttk.Label(parity_row, text="Stop:", width=5, style="App.TLabel").pack(side="left")
        ttk.Combobox(
            parity_row, textvariable=self.stop_bits, values=STOP_BITS_OPTIONS,
            state="readonly", style="App.TCombobox", width=5
        ).pack(side="left", padx=(4, 0))

        # ----------------- ACTION BUTTONS -----------------
        btn_frame = ttk.Frame(body, style="Panel.TFrame")
        btn_frame.pack(fill="x", pady=(8, 4))

        self.connect_btn = ttk.Button(
            btn_frame, text="▶ Подключить", command=self.open_rtu, style="App.TButton"
        )
        self.connect_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.disconnect_btn = ttk.Button(
            btn_frame, text="■ Отключить", command=self.close, style="Secondary.TButton", state="disabled"
        )
        self.disconnect_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # ----------------- TEST CONNECTION -----------------
        test_frame = ttk.Frame(body, style="Panel.TFrame")
        test_frame.pack(fill="x", pady=(8, 4))

        self.test_btn = ttk.Button(
            test_frame, text="🔍 Тест связи", command=self.test_connection,
            style="Secondary.TButton", state="disabled"
        )
        self.test_btn.pack(fill="x")

        # ----------------- ACTIVE CONNECTION INFO -----------------
        self.info_frame = ttk.LabelFrame(body, text="Активное подключение", style="Card.TLabelframe")
        self.info_frame.pack(fill="x", pady=(12, 0))
        self.info_frame.pack_forget()

        self.info_text = tk.Text(
            self.info_frame, height=5, width=40, state="disabled",
            font=("Consolas", 9), bg="#0f1721", fg="#eef3f8", insertbackground="#eef3f8",
            relief="flat", padx=8, pady=4, bd=0, highlightthickness=0
        )
        self.info_text.pack(fill="x", padx=4, pady=4)

        # ----------------- LOG AREA -----------------
        log_frame = ttk.LabelFrame(body, text="События", style="Card.TLabelframe")
        log_frame.pack(fill="x", pady=(12, 0))

        self.log_text = tk.Text(
            log_frame, height=4, width=40, state="disabled",
            font=("Consolas", 9), bg="#0f1721", fg="#eef3f8", insertbackground="#eef3f8",
            relief="flat", padx=8, pady=4, bd=0, highlightthickness=0
        )
        self.log_text.pack(fill="x", padx=4, pady=4)

        body.columnconfigure(0, weight=1)

    # =========================================================
    # STATUS INDICATOR & UI STATE
    # =========================================================

    def _draw_status_indicator(self):
        """Рисует цветной индикатор статуса"""
        self.status_indicator.delete("all")
        color, _ = self.STATUS_COLORS.get(self._connection_state, self.STATUS_COLORS["disconnected"])
        
        self.status_indicator.create_oval(2, 2, 18, 18, outline=color, width=2)
        self.status_indicator.create_oval(5, 5, 15, 15, fill=color, outline="")
        
        if self._connection_state == "connecting":
            self.status_indicator.after(300, self._draw_status_indicator)

    def _update_ui_state(self):
        """Обновляет UI в соответствии с состоянием"""
        state = self._connection_state
        
        status_texts = {
            "disconnected": ("Статус: Не подключено", ""),
            "connecting": ("Статус: Обработка...", "Пожалуйста, подождите"),
            "connected": ("Статус: ● Подключено", self._format_status_detail()),
            "error": ("Статус: ✗ Ошибка", self._last_status_info.get("error", "")),
        }
        text, detail = status_texts.get(state, status_texts["disconnected"])
        self.status_label.config(text=text)
        self.status_detail.config(text=detail)
        
        self._draw_status_indicator()
        
        # Управление кнопками
        if state == "connected":
            self.connect_btn.config(state="disabled")
            self.disconnect_btn.config(state="normal")
            self.test_btn.config(state="normal")
            self.port_combo.config(state="disabled")
            self.info_frame.pack(fill="x", pady=(12, 0))
        elif state == "connecting":
            self.connect_btn.config(state="disabled")
            self.disconnect_btn.config(state="disabled")
            self.test_btn.config(state="disabled")
            self.port_combo.config(state="disabled")
        else:
            self.connect_btn.config(state="normal")
            self.disconnect_btn.config(state="disabled")
            self.test_btn.config(state="disabled")
            self.port_combo.config(state="readonly")
            self.info_frame.pack_forget()

    def _format_status_detail(self) -> str:
        info = self._last_status_info
        if not info:
            return ""
        conn_type = info.get("type", "unknown").upper()
        if conn_type == "RTU":
            return f"{info.get('serial_port')} @ {info.get('baud_rate')} baud, {info.get('stop_bits')} stop"
        elif conn_type == "TCP":
            return f"{info.get('host')}:{info.get('port')}"
        return conn_type

    # =========================================================
    # STATUS POLLING (ИСПРАВЛЕНО)
    # =========================================================

    def _start_status_poll(self):
        if self._status_poll_active:
            return
        self._status_poll_active = True
        self._poll_status()

    def _stop_status_poll(self):
        self._status_poll_active = False

    def _poll_status(self):
        if not self._status_poll_active:
            return

        try:
            resp = self.client.transport_status()
            
            if "error" not in resp:
                result = resp.get("result", {})
                is_active = bool(result.get("active"))
                
                # 🔹 ЖЕСТКАЯ СИНХРОНИЗАЦИЯ С СЕРВЕРОМ
                if is_active:
                    if self._connection_state != "connected":
                        self._connection_state = "connected"
                        self._last_status_info = result
                        self._log_event("✓ Транспорт подключён", "success")
                        self._update_info_panel(result)
                else:
                    # Если сервер говорит "не активен", мы ПРИНУДИТЕЛЬНО сбрасываем состояние
                    if self._connection_state != "disconnected":
                        self._connection_state = "disconnected"
                        self._last_status_info = {}
                        self._log_event("✗ Транспорт отключён", "warning")
                        self.info_text.config(state="normal")
                        self.info_text.delete("1.0", "end")
                        self.info_text.config(state="disabled")
            else:
                # Ошибка запроса статуса
                if self._connection_state == "connected":
                    self._connection_state = "error"
                    self._last_status_info["error"] = resp.get("error", "unknown")
                    self._log_event(f"✗ Ошибка опроса: {resp['error']}", "error")
                    
        except Exception as e:
            self._connection_state = "error"
            self._last_status_info["error"] = str(e)
            self._log_event(f"✗ Исключение: {e}", "error")
        finally:
            self._update_ui_state()
            self.after(self._status_poll_interval, self._poll_status)

    def _update_info_panel(self, info: dict):
        lines = [f"Тип: {info.get('type', 'unknown').upper()}"]
        if info.get("type") == "rtu":
            lines.extend([
                f"Порт: {info.get('serial_port', 'N/A')}",
                f"Скорость: {info.get('baud_rate', 0)} baud",
                f"Stop bits: {info.get('stop_bits', 1)}",
                f"Parity: {info.get('parity', 'none')}",
            ])
        elif info.get("type") == "tcp":
            lines.extend([
                f"Host: {info.get('host', 'N/A')}",
                f"Port: {info.get('port', 0)}",
            ])
        
        self.info_text.config(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("end", "\n".join(lines))
        self.info_text.config(state="disabled")

    # =========================================================
    # LOGGING
    # =========================================================

    def _log_event(self, message: str, level: str = "info"):
        timestamp = time.strftime("%H:%M:%S")
        colors = {
            "success": "#66BB6A",
            "warning": "#FFA726",
            "error": "#EF5350",
            "info": "#90A4AE",
        }
        color = colors.get(level, colors["info"])
        
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{timestamp}] ", "timestamp")
        self.log_text.insert("end", f"{message}\n", level)
        self.log_text.tag_configure("timestamp", foreground="#546E7A")
        self.log_text.tag_configure(level, foreground=color)
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        
        if self.on_log:
            self.on_log(f"[Transport] {message}")

    def _notify(self, msg: str, is_error: bool = False):
        self._log_event(msg, "error" if is_error else "info")
        if is_error:
            messagebox.showerror("Transport Error", msg)

    # =========================================================
    # PORT MANAGEMENT
    # =========================================================

    def refresh_ports(self):
        self._log_event("🔄 Поиск портов...")
        
        resp = self.client.serial_ports()
        if "error" in resp:
            self.port_combo["values"] = []
            self.port.set("")
            self._notify(f"Ошибка: {resp['error']}", is_error=True)
            return

        raw_ports = resp.get("result", [])
        ports = raw_ports.get("ports", []) if isinstance(raw_ports, dict) else raw_ports
        ports = [str(p) for p in ports]
        self.port_combo["values"] = ports

        if ports:
            current = self.port.get()
            if current not in ports:
                self.port.set(ports[0])
            self._log_event(f"✓ Найдено портов: {len(ports)}", "success")
        else:
            self.port.set("")
            self._log_event("⚠ Порты не найдены", "warning")

    # =========================================================
    # CONNECTION CONTROL (ИСПРАВЛЕНО)
    # =========================================================

    def open_rtu(self):
        port = self.port.get().strip()
        if not port:
            self._notify("Выберите COM-порт", is_error=True)
            return

        try:
            baud = int(self.baud.get())
            stop_bits = int(self.stop_bits.get())
            parity = self.parity.get().strip().lower()
        except ValueError as e:
            self._notify(f"Неверный параметр: {e}", is_error=True)
            return

        self._connection_state = "connecting"
        self._update_ui_state()
        self._log_event(f"🔌 Подключение: {port} @ {baud} baud...")

        self.after(10, lambda: self._do_open_rtu(port, baud, stop_bits, parity))

    def _do_open_rtu(self, port: str, baud: int, stop_bits: int, parity: str):
        try:
            resp = self.client.open_rtu(port, baud=baud, stop_bits=stop_bits, parity=parity)

            if "error" in resp:
                self._connection_state = "error"
                self._last_status_info["error"] = resp["error"]
                self._notify(f"Ошибка подключения: {resp['error']}", is_error=True)
            else:
                self._log_event("✓ Запрос на подключение отправлен", "success")
                # Опрос сам обновит состояние на Connected через 1-2 сек
        except Exception as e:
            self._connection_state = "error"
            self._last_status_info["error"] = str(e)
            self._notify(f"Исключение: {e}", is_error=True)
        finally:
            self._update_ui_state()

    def close(self):
        self._log_event("🔌 Отключение...")
        # 🔹 СРАЗУ меняем состояние, чтобы интерфейс не висел
        self._connection_state = "disconnecting" 
        self._update_ui_state()
        
        self.after(10, lambda: self._do_close())

    def _do_close(self):
        try:
            resp = self.client.close_transport()
            if "error" in resp:
                self._notify(f"Ошибка отключения: {resp['error']}", is_error=True)
                self._connection_state = "error"
            else:
                self._log_event("✓ Запрос на отключение отправлен", "success")
                # 🔹 ЯВНЫЙ СБРОС СОСТОЯНИЯ
                self._connection_state = "disconnected"
                self._last_status_info = {}
                # Очищаем панель инфо сразу
                self.info_text.config(state="normal")
                self.info_text.delete("1.0", "end")
                self.info_text.config(state="disabled")
        except Exception as e:
            self._notify(f"Исключение: {e}", is_error=True)
            self._connection_state = "error"
        finally:
            self._update_ui_state()

    # =========================================================
    # TEST CONNECTION
    # =========================================================

    def test_connection(self):
        if self._connection_state != "connected":
            self._notify("Сначала подключитесь к порту", is_error=True)
            return

        self._log_event("🔍 Тест связи (ping)...")
        self.test_btn.config(state="disabled", text="⏳ Проверка...")

        def _do_test():
            try:
                start = time.time()
                resp = self.client.ping()
                elapsed = (time.time() - start) * 1000

                if "error" not in resp and resp.get("result", {}).get("status") == "ok":
                    self._log_event(f"✓ Ping: OK ({elapsed:.0f} мс)", "success")
                    messagebox.showinfo("Тест связи", f"Устройство отвечает!\nВремя: {elapsed:.0f} мс")
                else:
                    err = resp.get("error", "unknown")
                    self._log_event(f"✗ Ping failed: {err}", "error")
                    messagebox.showwarning("Тест связи", f"Нет ответа от устройства:\n{err}")
            except Exception as e:
                self._log_event(f"✗ Исключение при тесте: {e}", "error")
                messagebox.showerror("Тест связи", f"Ошибка: {e}")
            finally:
                self.test_btn.config(state="normal", text="🔍 Тест связи")

        self.after(10, _do_test)

    # =========================================================
    # CLEANUP
    # =========================================================

    def destroy(self):
        self._stop_status_poll()
        super().destroy()