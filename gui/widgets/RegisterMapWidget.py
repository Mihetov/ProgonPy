import csv
import struct
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List, Dict, Any, Optional


class RegisterMapWidget(ttk.LabelFrame):
    """Виджет карты регистров Modbus — упрощённая версия"""
    
    IS_APP_WIDGET = True
    PANEL_TITLE = "2.Карта регистров"

    TYPE_REGISTER_COUNT = {
        "Float32": 2, "Float": 2, "float32": 2,
        "Int32": 2, "UInt32": 2, "int32": 2, "uint32": 2,
        "String": 32, "TCP56": 4,
        "Int16": 1, "UInt16": 1, "Word": 1,
        "Int8": 1, "Byte": 1, "Array": 32,
    }

    def __init__(self, parent, client, poller=None, on_log=None):
        super().__init__(parent, text=self.PANEL_TITLE, style="Card.TLabelframe")

        self.client = client
        self.poller = poller
        self.on_log = on_log

        self.rows: List[Dict[str, Any]] = []
        self.transport_online = False

        # Настройки режима
        self.slave_mode = tk.StringVar(value="broadcast")
        self.slave_id = tk.StringVar(value="1")
        self.search_var = tk.StringVar()

        # Состояние операций
        self._bulk_read_active = False
        self._bulk_index = 0
        self._bulk_delay_ms = 40
        self._bulk_errors = 0

        # Опрос транспорта
        self._transport_poll_active = False
        self._transport_poll_interval = 3000

        self._build()
        self.after(300, self._check_transport_status)

    # =========================================================
    # UI BUILD
    # =========================================================

    def _build(self):
        body = ttk.Frame(self, style="Panel.TFrame")
        body.pack(fill="both", expand=True)

        # ----------------- TOP PANEL -----------------
        top = ttk.Frame(body, style="Panel.TFrame")
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="Режим", style="App.TLabel").grid(row=0, column=0, sticky="w")

        ttk.Radiobutton(top, text="Slave", variable=self.slave_mode, value="single",
                        command=self._on_slave_mode_changed).grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(top, text="Broadcast", variable=self.slave_mode, value="broadcast",
                        command=self._on_slave_mode_changed).grid(row=0, column=2, sticky="w")

        ttk.Label(top, text="Slave ID", style="App.TLabel").grid(row=0, column=3, padx=(16, 4))
        
        self.slave_id_frame = ttk.Frame(top)
        self.slave_id_frame.grid(row=0, column=4, sticky="w")
        self._build_slave_id_input()

        ttk.Label(top, text="Поиск", style="App.TLabel").grid(row=0, column=5, padx=(16, 4))
        search = ttk.Entry(top, textvariable=self.search_var, style="App.TEntry")
        search.grid(row=0, column=6, sticky="ew")
        search.bind("<KeyRelease>", self._apply_filter)

        ttk.Button(top, text="CSV", command=self.load_csv, style="Secondary.TButton").grid(row=0, column=7, padx=(10, 0))
        ttk.Button(top, text="Read All", command=self.read_all, style="App.TButton").grid(row=0, column=8, padx=(10, 0))
        # ✅ Оставлена только кнопка записи выбранного
        ttk.Button(top, text="Write Selected", command=self.write_selected,
                   style="Primary.TButton").grid(row=0, column=9, padx=(4, 0))

        top.columnconfigure(6, weight=1)

        # ----------------- STATUS LABEL -----------------
        self.status_label = ttk.Label(body, text="Transport: UNKNOWN", padding=(8, 4))
        self.status_label.pack(fill="x", padx=8, pady=(0, 4))

        # ----------------- TABLE -----------------
        columns = ("address", "name", "type", "min", "max", "description", "value")
        table_frame = ttk.Frame(body)
        table_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        headers = {"address": "Address", "name": "Name", "type": "Type",
                   "min": "Min", "max": "Max", "description": "Description", "value": "Value"}
        widths = {"address": 90, "name": 180, "type": 70, "min": 70,
                  "max": 70, "description": 260, "value": 140}

        for col in columns:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=widths[col])

        self.tree.bind("<Double-1>", self._edit_value)

        # ----------------- BOTTOM PANEL -----------------
        bottom = ttk.Frame(body, style="Panel.TFrame")
        bottom.pack(fill="x", padx=8, pady=(0, 8))

        ttk.Button(bottom, text="Read Selected", command=self.read_selected,
                   style="Secondary.TButton").pack(side="left", padx=(0, 4))
        ttk.Button(bottom, text="Write Selected", command=self.write_selected,
                   style="Secondary.TButton").pack(side="left")
        ttk.Button(bottom, text="Stop", command=self.stop_bulk,
                   style="Secondary.TButton").pack(side="left", padx=(4, 0))

    # =========================================================
    # SLAVE ID INPUT SWITCHING
    # =========================================================

    def _build_slave_id_input(self):
        for widget in self.slave_id_frame.winfo_children():
            widget.destroy()
        if self.slave_mode.get() == "broadcast":
            self.slave_id_combo = ttk.Combobox(self.slave_id_frame, values=["0xFE", "0xFF"],
                                               state="readonly", width=6, style="App.TEntry")
            self.slave_id_combo.set("0xFF")
            self.slave_id_combo.pack()
        else:
            self.slave_id_entry = ttk.Entry(self.slave_id_frame, textvariable=self.slave_id,
                                            width=8, style="App.TEntry")
            self.slave_id_entry.pack()

    def _on_slave_mode_changed(self):
        self._build_slave_id_input()

    def _slave(self) -> int:
        if self.slave_mode.get() == "broadcast":
            val = self.slave_id_combo.get() if hasattr(self, 'slave_id_combo') else "0xFF"
            return int(val, 16)
        try:
            return int(self.slave_id.get())
        except (ValueError, TypeError):
            return 1

    # =========================================================
    # LOGGING
    # =========================================================

    def _notify(self, msg: str, is_error: bool = False):
        if self.on_log:
            self.on_log(msg)
        if is_error:
            messagebox.showerror("Register Map", msg)

    # =========================================================
    # TRANSPORT STATUS
    # =========================================================

    def _check_transport_status(self):
        if self._transport_poll_active:
            self.after(self._transport_poll_interval, self._check_transport_status)
            return
        self._transport_poll_active = True
        try:
            resp = self.client.transport_status()
            result = resp.get("result", {})
            online = bool(result.get("active")) if isinstance(result, dict) else False
            if online != self.transport_online:
                self.transport_online = online
                self._update_transport_display(result)
        except Exception as e:
            self.transport_online = False
            self._update_transport_display({}, error=str(e))
        finally:
            self._transport_poll_active = False
            self.after(self._transport_poll_interval, self._check_transport_status)

    def _update_transport_display(self, result: Dict[str, Any], error: str = None):
        if not self.transport_online or error:
            self.status_label.config(text="Transport: DISCONNECTED" + (f" ({error})" if error else ""))
            return
        conn_type = result.get("type", "unknown").upper()
        if conn_type == "RTU":
            text = f"✓ RTU: {result.get('serial_port', 'N/A')} @ {result.get('baud_rate', 0)} baud"
        elif conn_type == "TCP":
            text = f"✓ TCP: {result.get('host', 'N/A')}:{result.get('port', 0)}"
        else:
            text = f"✓ {conn_type}: connected"
        self.status_label.config(text=text)

    # =========================================================
    # HELPERS
    # =========================================================

    def _get_count_for_type(self, typ: str) -> int:
        return self.TYPE_REGISTER_COUNT.get(typ, 1)

    def _parse_numeric(self, value: str) -> Optional[float]:
        try:
            value = value.strip()
            if value.lower().startswith("0x"):
                return int(value, 16)
            return float(value)
        except:
            return None

    def _validate_range(self, reg: Dict[str, Any], value: Any) -> bool:
        """Проверка значения на соответствие мин/макс"""
        try:
            min_val = reg.get("min", "")
            max_val = reg.get("max", "")
            typ = reg.get("type", "")
            
            if not min_val and not max_val:
                return True
            
            # Специальная обработка для Array: проверяем каждый байт
            if typ == "Array":
                bytes_str = str(value).strip()
                if not bytes_str:
                    return True
                byte_values = bytes_str.split()
                min_b = self._parse_numeric(min_val)
                max_b = self._parse_numeric(max_val)
                for b_str in byte_values:
                    b = self._parse_numeric(b_str)
                    if b is None:
                        return False
                    if min_b is not None and b < min_b:
                        return False
                    if max_b is not None and b > max_b:
                        return False
                return True
            
            # Стандартная проверка для чисел
            num = self._parse_numeric(str(value))
            if num is None:
                return False
            if min_val:
                min_num = self._parse_numeric(min_val)
                if min_num is not None and num < min_num:
                    return False
            if max_val:
                max_num = self._parse_numeric(max_val)
                if max_num is not None and num > max_num:
                    return False
            return True
        except:
            return True

    # =========================================================
    # CSV LOADING
    # =========================================================

    def load_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        self.rows.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

        encodings = ["utf-8", "utf-8-sig", "cp1251", "windows-1251", "latin1"]
        last_error = None
        loaded = False

        for enc in encodings:
            try:
                with open(path, "r", encoding=enc) as f:
                    reader = csv.reader(f, delimiter=";")
                    next(reader, None)
                    for row in reader:
                        if not row or not row[0].strip():
                            continue
                        try:
                            addr_str = row[0].strip()
                            address = int(addr_str, 16) if addr_str.lower().startswith("0x") else int(addr_str)
                        except ValueError:
                            continue
                        bytes_val = 2
                        if len(row) > 4 and row[4].strip():
                            try:
                                bytes_val = int(row[4])
                            except ValueError:
                                bytes_val = 2
                        reg_count = max(1, (bytes_val + 1) // 2)
                        reg = {
                            "address": address, "name": row[1] if len(row) > 1 else "",
                            "type": row[5] if len(row) > 5 else "Int16", "bytes": bytes_val,
                            "reg_count": reg_count, "min": row[6] if len(row) > 6 else "",
                            "max": row[7] if len(row) > 7 else "", "description": row[8] if len(row) > 8 else "",
                            "value": row[10] if len(row) > 10 else ""
                        }
                        self.rows.append(reg)
                loaded = True
                self._notify(f"CSV loaded ({enc}), registers: {len(self.rows)}")
                break
            except Exception as e:
                last_error = e

        if not loaded:
            self._notify(f"CSV load failed: {last_error}", is_error=True)
            return
        self._refresh_table()

    # =========================================================
    # FILTER & REFRESH
    # =========================================================

    def _apply_filter(self, event=None):
        self._refresh_table()

    def _refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        filt = self.search_var.get().lower().strip()
        for index, reg in enumerate(self.rows):
            text = f"{reg['name']} {reg['description']}".lower()
            if filt and filt not in text:
                continue
            self.tree.insert("", "end", iid=str(index), values=(
                f"0x{reg['address']:04X}", reg["name"], reg["type"],
                reg["min"], reg["max"], reg["description"], reg["value"]
            ))

    def _refresh_row(self, index: int):
        """Простое обновление строки без подсветки"""
        iid = str(index)
        if not self.tree.exists(iid):
            return
        reg = self.rows[index]
        self.tree.item(iid, values=(
            f"0x{reg['address']:04X}", reg["name"], reg["type"],
            reg["min"], reg["max"], reg["description"], reg["value"]
        ))

    # =========================================================
    # READ OPERATIONS
    # =========================================================

    def read_all(self):
        if self._bulk_read_active:
            self._notify("Read already active")
            return
        if not self.client.is_ready() or not self.transport_online:
            self._notify("Backend not ready" if not self.client.is_ready() else "Transport not connected", is_error=True)
            return
        self._bulk_read_active = True
        self._bulk_index = 0
        self._bulk_errors = 0
        self._notify("Bulk read started")
        self._read_next()

    def _read_next(self):
        if not self._bulk_read_active:
            return
        if self._bulk_index >= len(self.rows):
            self._bulk_read_active = False
            self._notify(f"Bulk read completed, errors: {self._bulk_errors}")
            return
        try:
            self._read_row(self._bulk_index)
        except Exception as e:
            self._notify(str(e), is_error=True)
        self._bulk_index += 1
        self.after(self._bulk_delay_ms, self._read_next)

    def read_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        self._read_row(int(sel[0]))

    def _read_row(self, index: int):
        if not self.client.is_ready() or not self.transport_online:
            return
        reg = self.rows[index]
        reg_type = reg.get("type", "Int16")
        count = reg.get("reg_count", self._get_count_for_type(reg_type))

        resp = self.client.read(slave=self._slave(), address=reg["address"],
                                count=count, input=False, timeout_ms=2000)

        if "error" in resp:
            self._bulk_errors += 1
            err_msg = resp.get("error", "unknown")
            if isinstance(err_msg, dict):
                err_msg = err_msg.get("message", str(err_msg))
            reg["value"] = f"ERR: {err_msg}"
            self._refresh_row(index)
            return

        result = resp.get("result", {})
        values = result.get("values") or result.get("data") or result.get("registers") or []
        if not values:
            self._bulk_errors += 1
            reg["value"] = "ERR: empty"
            self._refresh_row(index)
            return

        try:
            reg["value"] = self._decode_value(reg_type, values)
        except Exception as e:
            self._bulk_errors += 1
            reg["value"] = f"ERR: decode: {e}"
        self._refresh_row(index)

    # =========================================================
    # WRITE SELECTED ONLY
    # =========================================================

    def write_selected(self):
        """Запись только выбранной строки"""
        sel = self.tree.selection()
        if not sel:
            self._notify("No register selected", is_error=True)
            return
        
        index = int(sel[0])
        self._write_row(index)

    def _write_row(self, index: int):
        """Запись одного регистра"""
        if not self.client.is_ready():
            self._notify("Backend not ready", is_error=True)
            return
        if not self.transport_online:
            self._notify("Transport not connected", is_error=True)
            return

        reg = self.rows[index]

        # Валидация диапазона
        if not self._validate_range(reg, reg["value"]):
            self._notify(f"Value out of range for {reg['name']}", is_error=True)
            return

        try:
            values = self._encode_value(reg["type"], reg["value"])
        except Exception as e:
            reg["value"] = f"ERR: encode: {e}"
            self._refresh_row(index)
            return

        write_params = {"slave": self._slave(), "address": reg["address"]}
        if len(values) > 1:
            write_params["values"] = values
        else:
            write_params["value"] = values[0]

        resp = self.client.write(**write_params)

        if "error" in resp:
            err_msg = resp.get("error", "unknown")
            if isinstance(err_msg, dict):
                err_msg = err_msg.get("message", str(err_msg))
            reg["value"] = f"ERR: {err_msg}"
            self._notify(f"Write failed [{reg['name']}]: {err_msg}", is_error=True)
            self._refresh_row(index)
            return

        result = resp.get("result", {})
        if result.get("accepted"):
            self._notify(f"Written: {reg['name']}")
            # Перечитываем значение после записи для актуальности
            self._read_row(index)
        else:
            self._notify(f"Write acknowledged: {reg['name']}")

    # =========================================================
    # STOP BULK
    # =========================================================

    def stop_bulk(self):
        self._bulk_read_active = False
        self._notify("Bulk operation stopped")

    # =========================================================
    # CODEC: DECODE / ENCODE
    # =========================================================

    def _decode_value(self, typ: str, values: List[int]) -> Any:
        if not values:
            return ""
        try:
            if typ in ("Float32", "Float", "float32"):
                if len(values) < 2: raise ValueError("Float32 requires 2 registers")
                raw = struct.pack(">HH", values[0], values[1])
                return round(struct.unpack(">f", raw)[0], 5)
            if typ in ("Int32", "int32"):
                if len(values) < 2: raise ValueError("Int32 requires 2 registers")
                raw = struct.pack(">HH", values[0], values[1])
                return struct.unpack(">i", raw)[0]
            if typ in ("UInt32", "uint32"):
                if len(values) < 2: raise ValueError("UInt32 requires 2 registers")
                raw = struct.pack(">HH", values[0], values[1])
                return struct.unpack(">I", raw)[0]
            if typ in ("Int16", "int16"):
                v = values[0] & 0xFFFF
                return v - 0x10000 if v > 0x7FFF else v
            if typ in ("UInt16", "Word", "uint16"):
                return values[0] & 0xFFFF
            if typ == "Int8":
                v = values[0] & 0xFF
                return v - 256 if v > 127 else v
            if typ in ("Byte", "byte"):
                return values[0] & 0xFF
            if typ == "String":
                raw = b''.join(struct.pack(">H", v & 0xFFFF) for v in values)
                return raw.rstrip(b'\x00').decode('ascii', errors='replace').strip()
            if typ == "Array":
                bytes_list = []
                for reg in values:
                    bytes_list.append((reg >> 8) & 0xFF)
                    bytes_list.append(reg & 0xFF)
                return " ".join(str(b) for b in bytes_list)
            return " ".join(f"0x{v:04X}" for v in values)
        except Exception as e:
            return f"⚠ {e}"

    def _encode_value(self, typ: str, value) -> List[int]:
        try:
            if typ in ("Float32", "Float", "float32"):
                raw = struct.pack(">f", float(value))
                return list(struct.unpack(">HH", raw))
            if typ in ("Int32", "int32"):
                raw = struct.pack(">i", int(value))
                return list(struct.unpack(">HH", raw))
            if typ in ("UInt32", "uint32"):
                raw = struct.pack(">I", int(value) & 0xFFFFFFFF)
                return list(struct.unpack(">HH", raw))
            if typ in ("Int16", "int16"):
                return [int(value) & 0xFFFF]
            if typ in ("UInt16", "Word", "uint16"):
                return [int(value) & 0xFFFF]
            if typ == "Int8":
                return [(int(value) + 256) % 256]
            if typ in ("Byte", "byte"):
                return [int(value) & 0xFF]
            if typ == "String":
                s = str(value).encode('ascii', errors='replace')
                if len(s) % 2 != 0: s += b'\x00'
                return list(struct.unpack(">" + "H" * (len(s) // 2), s))
            if typ == "Array":
                raw_bytes = [int(x) & 0xFF for x in str(value).split() if x.strip()]
                if len(raw_bytes) % 2 != 0:
                    raw_bytes.append(0)
                registers = []
                for i in range(0, len(raw_bytes), 2):
                    reg = (raw_bytes[i] << 8) | raw_bytes[i+1]
                    registers.append(reg)
                return registers
            return [int(value) & 0xFFFF]
        except Exception as e:
            raise ValueError(f"Encode error ({typ}): {e}")

    # =========================================================
    # INLINE EDIT
    # =========================================================

    def _edit_value(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        column = self.tree.identify_column(event.x)
        if column != "#7":
            return

        x, y, w, h = self.tree.bbox(item, column)
        current = self.tree.set(item, "value")
        index = int(item)
        reg = self.rows[index]

        entry = ttk.Entry(self.tree)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, current)
        entry.focus()
        
        if reg.get("type") == "Array":
            entry.insert("end", "  # байты: 0 255 128")
            entry.select_range(len(current), "end")

        def save(event=None):
            value = entry.get().split("#")[0].strip()
            reg["value"] = value
            self._refresh_row(index)
            entry.destroy()

        entry.bind("<Return>", save)
        entry.bind("<FocusOut>", save)