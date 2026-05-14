# -*- coding: utf-8 -*-
"""
Модуль тестирования устройств (режим стенда)
Архитектура: Model-View, BackendClient, асинхронные операции
"""

import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Optional, Callable
from enum import Enum, auto


class DeviceType(Enum):
    """Типы устройств для тестирования"""
    NORMAL = 1      # Обычное (только цифры)
    SPECIAL = 2     # Со спецсимволами
    SLIDER = 3      # Со слайдером и шкалой


class DiscoveredDevice:
    """Модель найденного устройства"""
    def __init__(self, address: int, device_type: DeviceType = DeviceType.NORMAL, basis: int = 4):
        self.address = address
        self.device_type = device_type
        self.basis = basis  # 🔹 Количество ячеек индикатора (из регистра 0xF004)
        self.name = f"Устройство #{address} ({device_type.name}, {basis} ячейки)"
        self.last_sent: str = ""      # Последнее отправленное значение
        self.last_received: str = ""  # Последний ответ от устройства
        self.error_count: int = 0 
    
    def __repr__(self):
        return f"DiscoveredDevice(addr={self.address}, type={self.device_type.name}, basis={self.basis})"


class DeviceTestWidget(ttk.LabelFrame):
    """Виджет тестирования устройств в режиме стенда"""
    
    IS_APP_WIDGET = True
    PANEL_TITLE = "3.Тест устройств"

    # Адреса регистров (константы из спецификации)
    REG_DEVICE_ID = 0xF000      # Чтение адреса устройства
    REG_SEGMENTS = 0x0000       # Управление сегментами индикатора
    REG_SPECIAL = 0xC000        # Управление спецсимволами
    REG_SLIDER = 0xC100         # Управление слайдером (Float)
    REG_SCALE_BASE = 0xC000     # База регистров шкалы (4 регистра)
    REG_COLOR = 0xE002          # Цвет подсветки
    REG_obasis = 0xF004         # O-basis
    REG_sdescript = 0xF800      # Описание устройства
    # Параметры сканирования по умолчанию
    MAX_BASIS = 8
    MAX_SEGMENT_REGS = 4
    DEFAULT_SCAN_START = 1
    DEFAULT_SCAN_END = 247
    SCAN_TIMEOUT_MS = 500

    def __init__(self, parent, client, poller=None, on_log=None):
        super().__init__(parent, text=self.PANEL_TITLE, style="Card.TLabelframe")

        self.client = client
        self.poller = poller
        self.on_log = on_log

        # Модель данных
        self.devices: List[DiscoveredDevice] = []
        self.transport_online = False

        # Настройки сканирования
        self.scan_start = tk.IntVar(value=self.DEFAULT_SCAN_START)
        self.scan_end = tk.IntVar(value=self.DEFAULT_SCAN_END)

        # Состояние теста
        self._test_active = False
        self._test_thread: Optional[tk.after] = None
        self._test_cycle = 0
        self._current_color = 0

        # Тайминги теста
        self._step_delay_ms = 200
        self._cycle_delay_ms = 1000

        self._build()
        self.after(300, self._check_transport)

    # =========================================================
    # UI BUILD
    # =========================================================

    def _build(self):
        body = ttk.Frame(self, style="Panel.TFrame")
        body.pack(fill="both", expand=True, padx=8, pady=8)

        # ----------------- CONNECTION STATUS -----------------
        conn_frame = ttk.Frame(body)
        conn_frame.pack(fill="x", pady=(0, 8))

        self.status_label = ttk.Label(
            conn_frame,
            text="Transport: UNKNOWN",
            style="Offline.TLabel"
        )
        self.status_label.pack(side="left")

        ttk.Button(
            conn_frame,
            text="Refresh",
            command=self._check_transport,
            style="Secondary.TButton"
        ).pack(side="right")

        # ----------------- SCAN SETTINGS -----------------
        scan_frame = ttk.LabelFrame(body, text="Сканирование")
        scan_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(scan_frame, text="Диапазон адресов:").grid(row=0, column=0, sticky="w", padx=(8, 4))
        
        ttk.Entry(scan_frame, textvariable=self.scan_start, width=6).grid(row=0, column=1, sticky="w")
        ttk.Label(scan_frame, text="—").grid(row=0, column=2)
        ttk.Entry(scan_frame, textvariable=self.scan_end, width=6).grid(row=0, column=3, sticky="w")
        
        ttk.Button(
            scan_frame,
            text="Сканировать",
            command=self._start_scan,
            style="Primary.TButton"
        ).grid(row=0, column=4, padx=(20, 8))

        # ----------------- DEVICE LIST -----------------
        list_frame = ttk.LabelFrame(body, text="Найденные устройства")
        list_frame.pack(fill="both", expand=True, pady=(0, 8))

        columns = ("address", "type", "name")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.heading("address", text="Адрес")
        self.tree.heading("type", text="Тип")
        self.tree.heading("name", text="Описание")
        
        self.tree.column("address", width=80, anchor="center")
        self.tree.column("type", width=120, anchor="center")
        self.tree.column("name", width=200)

        # Контекстное меню для удаления
        self._bind_context_menu()

        # ----------------- TEST CONTROLS -----------------
        test_frame = ttk.Frame(body)
        test_frame.pack(fill="x", pady=(0, 8))

        self.test_btn = ttk.Button(
            test_frame,
            text="▶ Начать тест",
            command=self._toggle_test,
            style="Success.TButton",
            state="disabled"
        )
        self.test_btn.pack(side="left", padx=(0, 8))

        ttk.Button(
            test_frame,
            text="✕ Очистить список",
            command=self._clear_devices,
            style="Secondary.TButton"
        ).pack(side="left")

        self.cycle_label = ttk.Label(test_frame, text="")
        self.cycle_label.pack(side="right")

        # ----------------- LOG AREA -----------------
        log_frame = ttk.LabelFrame(body, text="Лог")
        log_frame.pack(fill="x")

        self.log_text = tk.Text(
            log_frame,
            height=4,
            width=50,
            state="disabled",
            font=("Consolas", 9)
        )
        self.log_text.pack(fill="x", padx=4, pady=4)

    def _bind_context_menu(self):
        """Контекстное меню: удалить устройство"""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Удалить", command=self._remove_selected)
        
        def show_menu(event):
            if self.tree.selection():
                menu.tk_popup(event.x_root, event.y_root)
        
        self.tree.bind("<Button-3>", show_menu)
        self.tree.bind("<Delete>", lambda e: self._remove_selected())

    # =========================================================
    # TRANSPORT & LOGGING
    # =========================================================

    def _check_transport(self):
        """Проверка статуса транспорта"""
        try:
            resp = self.client.transport_status()
            result = resp.get("result", {})
            online = bool(result.get("active"))
            
            if online != self.transport_online:
                self.transport_online = online
                self._update_status_display(result)
                
        except Exception as e:
            self.transport_online = False
            self.status_label.config(text="Transport: ERROR")
            self._log(f"Transport check error: {e}")

    def _update_status_display(self, result: dict):
        """Обновление отображения статуса"""
        if not self.transport_online:
            self.status_label.config(text="Transport: DISCONNECTED", style="Offline.TLabel")
            self.test_btn.config(state="disabled")
            return

        conn_type = result.get("type", "unknown").upper()
        if conn_type == "RTU":
            text = f"✓ RTU: {result.get('serial_port')} @ {result.get('baud_rate')} baud"
        elif conn_type == "TCP":
            text = f"✓ TCP: {result.get('host')}:{result.get('port')}"
        else:
            text = f"✓ {conn_type}: connected"
        
        self.status_label.config(text=text, style="Online.TLabel")
        # Кнопка теста активна, если есть устройства
        self.test_btn.config(state="normal" if self.devices else "disabled")

    def _log(self, message: str):
        """Добавление сообщения в лог"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        
        if self.on_log:
            self.on_log(f"[DeviceTest] {message}")

    def _notify(self, message: str, is_error: bool = False):
        """Уведомление пользователя"""
        self._log(message)
        if is_error:
            messagebox.showerror(self.PANEL_TITLE, message)

    # =========================================================
    # DEVICE LIST MANAGEMENT
    # =========================================================

    def _clear_devices(self):
        """Очистка списка устройств"""
        if self._test_active:
            self._toggle_test()  # Остановить тест если идёт
        
        self.devices.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._log("Список устройств очищен")
        self.test_btn.config(state="disabled")

    def _remove_selected(self):
        """Удаление выбранных устройств"""
        selected = self.tree.selection()
        if not selected:
            return
        
        # Собираем индексы для удаления (в обратном порядке)
        indices = sorted([int(iid) for iid in selected], reverse=True)
        for idx in indices:
            if 0 <= idx < len(self.devices):
                self.devices.pop(idx)
            self.tree.delete(str(idx))
        
        # Перестроить iid после удаления
        self._refresh_device_list()
        self._log(f"Удалено устройств: {len(indices)}")
        self.test_btn.config(state="normal" if self.devices else "disabled")

    def _refresh_device_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        for idx, dev in enumerate(self.devices):
            type_names = {
                DeviceType.NORMAL: "Обычное",
                DeviceType.SPECIAL: "Со спецсимволами",
                DeviceType.SLIDER: "Со слайдером"
            }
            # 🔹 Показываем basis в описании
            basis_text = f"{dev.basis}яч" if dev.basis != 4 else ""  # не показываем если стандарт
            name_suffix = f" [{basis_text}]" if basis_text else ""
            self.tree.insert("", "end", iid=str(idx), values=(
                f"0x{dev.address:04X}",
                type_names.get(dev.device_type, "?"),
                f"{dev.name}{name_suffix}"
            ))
    def _cells_to_registers(self, cells: List[int]) -> List[int]:
        """
        Конвертация списка значений ячеек (0-255) в список 16-битных регистров
        :param cells: [cell0, cell1, ..., cellN] где каждый 0-255
        :return: [reg0, reg1, ...] для записи последовательно начиная с REG_SEGMENTS
        """
        regs = []
        # Каждая пара ячеек → один регистр (старший байт = чётная ячейка, младший = нечётная)
        for i in range(0, len(cells), 2):
            high = cells[i] if i < len(cells) else 0
            low = cells[i+1] if i+1 < len(cells) else 0
            reg = (high << 8) | low
            regs.append(reg)
        return regs
    def _registers_to_cells(self, regs: List[int], basis: int) -> List[int]:
        """
        Обратная конвертация: регистры → список ячеек
        :param regs: список 16-битных значений
        :param basis: сколько ячеек нужно извлечь
        :return: список из basis значений 0-255
        """
        cells = []
        for reg in regs:
            cells.append((reg >> 8) & 0xFF)  # старший байт
            cells.append(reg & 0xFF)          # младший байт
            if len(cells) >= basis:
                break
        return cells[:basis]
    def _encode_cells_basis(self, cells: List[int], basis: int) -> tuple:
        """
        Кодирование списка ячеек в два 16-битных регистра с учётом basis
        :param cells: список значений ячеек (0-255)
        :param basis: количество значимых ячеек (1-8)
        :return: (reg1, reg2)
        """
        # Дополняем до 4 ячеек нулями для совместимости с 2 регистрами
        while len(cells) < 4:
            cells.append(0)
        # Берём только первые 4 для кодирования в 2 регистра
        return self._encode_four_numbers(cells[0], cells[1], cells[2], cells[3])

    def _blink_device(self, address: int, duration_ms: int = 3000, interval_ms: int = 300, basis: int = 4):
        """Мигание с учётом количества ячеек"""
        blink_state = {"active": True, "on": True}
        
        # 🔹 Предварительно кодируем "включено" и "выключено"
        cells_on = [0xFF] * basis  # все сегменты включены
        regs_on = self._cells_to_registers(cells_on)
        regs_off = [0] * ((basis + 1) // 2)  # все выключено
        
        def _toggle():
            regs = regs_on if blink_state["on"] else regs_off
            for i, reg_val in enumerate(regs):
                self.client.write(slave=address, address=self.REG_SEGMENTS + i, value=reg_val)
            blink_state["on"] = not blink_state["on"]
        
        def _blink_step():
            if not blink_state["active"]:
                # Финальный сброс
                for i in range((basis + 1) // 2):
                    self.client.write(slave=address, address=self.REG_SEGMENTS + i, value=0)
                return
            _toggle()
            self.after(interval_ms, _blink_step)
        
        _blink_step()
        self.after(duration_ms, lambda: setattr(blink_state, "active", False) or _blink_step())
        
        def _stop():
            blink_state["active"] = False
        return _stop
    def _add_device_with_dialog(self, address: int) -> bool:
        """Диалог выбора типа устройства с миганием для идентификации"""
        # Проверка: не добавлено ли уже
        if any(d.address == address for d in self.devices):
            self._log(f"Устройство 0x{address:04X} уже в списке")
            return False
        basis = 4  # default
        try:
            resp = self.client.read(slave=address, address=self.REG_obasis, count=1, timeout_ms=200)
            if "error" not in resp:
                values = resp.get("result", {}).get("values") or []
                if values and 1 <= values[0] <= self.MAX_BASIS:  # 🔹 Проверка на MAX_BASIS
                    basis = values[0]
                    self._log(f"  O-basis для 0x{address:04X}: {basis} ячейки")
                elif values:
                    self._log(f"  ⚠ O-basis={values[0]} вне диапазона 1-{self.MAX_BASIS}, используем 4")
        except Exception as e:
            self._log(f"  ⚠ Не удалось прочитать O-basis: {e}")
        # 🔹 Запускаем мигание для визуальной идентификации
        stop_blink = self._blink_device(address, duration_ms=5000, basis=basis)
        
        # Диалог выбора типа
        dialog = tk.Toplevel(self)
        dialog.title(f"Устройство 0x{address:04X}")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Центрирование
        dialog.update_idletasks()
        x = self.winfo_rootx() + self.winfo_width()//2 - 150
        y = self.winfo_rooty() + self.winfo_height()//2 - 100
        dialog.geometry(f"320x220+{x}+{y}")
        
        # Заголовок с подсказкой
        ttk.Label(dialog, text=f"Адрес: 0x{address:04X}", font=("Segoe UI", 10, "bold")).pack(pady=(15, 5))
        ttk.Label(dialog, text="⚡ Устройство должно мигать ⚡", foreground="#FF6B00").pack(pady=(0, 10))
        ttk.Label(dialog, text="Выберите тип устройства:").pack()
        
        var = tk.IntVar(value=1)
        types = [
            (1, "Обычное (только цифры)"),
            (2, "Со спецсимволами (цифры + символы)"),
            (3, "Со слайдером и шкалой")
        ]
        
        for val, desc in types:
            ttk.Radiobutton(dialog, text=desc, variable=var, value=val).pack(anchor="w", padx=50, pady=2)
        
        result = {"selected": None}
        
        def _cleanup_and_close():
            """Общая функция закрытия: останавливаем мигание + закрываем диалог"""
            stop_blink()  # ✅ Останавливаем мигание
            dialog.destroy()
        
        def on_ok():
            result["selected"] = DeviceType(var.get())
            _cleanup_and_close()
        
        def on_cancel():
            result["selected"] = None
            _cleanup_and_close()
        
        # Кнопки
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="OK", command=on_ok, style="Primary.TButton", width=10).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Отмена", command=on_cancel, width=10).pack(side="left", padx=10)
        
        # 🔹 Гарантированная остановка мигания при любом закрытии диалога
        dialog.protocol("WM_DELETE_WINDOW", _cleanup_and_close)
        
        # Ожидание ответа (блокирующее, но мигание работает через after)
        dialog.wait_window()
        
        # 🔹 Дополнительная страховка: если диалог закрыт, но мигание ещё идёт
        stop_blink()
        
        if result["selected"]:
            device = DiscoveredDevice(address, result["selected"], basis=basis)
            self.devices.append(device)
            self._refresh_device_list()
            self._log(f"✓ Добавлено: {device.name}")
            self.test_btn.config(state="normal")
            return True
        else:
            self._log(f"✗ Пропущено устройство 0x{address:04X}")
            return False

    # =========================================================
    # SCANNING
    # =========================================================

    def _start_scan(self):
        """Запуск сканирования"""
        if not self.transport_online:
            self._notify("Transport not connected", is_error=True)
            return
        
        # Очистка перед новым сканированием
        self._clear_devices()
        
        start = self.scan_start.get()
        end = self.scan_end.get()
        
        if not (1 <= start <= end <= 247):
            self._notify("Неверный диапазон адресов (1-247)", is_error=True)
            return
        
        self._log(f"Сканирование {start}–{end} (регистр 0x{self.REG_DEVICE_ID:04X})...")
        self._scan_next(start, end)

    def _scan_next(self, current: int, end: int):
        """Рекурсивное сканирование следующего адреса"""
        if current > end:
            self._log(f"Сканирование завершено. Найдено: {len(self.devices)}")
            return
        
        address = current
        self._log(f"Проверка адреса 0x{address:04X}...")
        
        # Чтение регистра 0xF000 для проверки наличия устройства
        resp = self.client.read(
            slave=address,
            address=self.REG_DEVICE_ID,
            count=1,
            timeout_ms=self.SCAN_TIMEOUT_MS
        )
        
        if "error" not in resp:
            result = resp.get("result", {})
            values = result.get("values") or result.get("data") or []
            
            if values and values[0] == address:
                self._log(f"✓ Ответ от 0x{address:04X}")
                # Диалог добавления (блокирующий)
                self._add_device_with_dialog(address)
            else:
                self._log(f"✗ Нет ответа или неверный ответ от 0x{address:04X}")
        else:
            self._log(f"✗ Ошибка запроса к 0x{address:04X}: {resp.get('error')}")
        
        # Следующий адрес с задержкой
        self.after(50, lambda: self._scan_next(current + 1, end))

    # =========================================================
    # STAND MODE TEST
    # =========================================================

    def _toggle_test(self):
        """Старт/стоп теста"""
        if self._test_active:
            self._stop_test()
        else:
            self._start_test()

    def _start_test(self):
        """Запуск режима стенда"""
        if not self.devices:
            self._notify("Нет устройств для теста", is_error=True)
            return
        if not self.transport_online:
            self._notify("Transport not connected", is_error=True)
            return
        
        self._test_active = True
        self._test_cycle = 0
        self._current_color = 0
        self.test_btn.config(text="⏹ Остановить тест", style="Danger.TButton")
        self._log("=== ЗАПУСК РЕЖИМА СТЕНДА ===")
        
        # Запуск первого шага теста
        self._test_step()

    def _stop_test(self):
        """Остановка теста"""
        self._test_active = False
        self.test_btn.config(text="▶ Начать тест", style="Success.TButton")
        self._log("Тест остановлен пользователем")
        
        # Сброс индикаторов на всех устройствах
        self._reset_all_devices()

    def _reset_all_devices(self):
        """Сброс всех индикаторов после остановки"""
        for dev in self.devices:
            try:
                # 🔹 Вычисляем сколько регистров нужно очистить
                num_regs = (dev.basis + 1) // 2
                for i in range(num_regs):
                    self.client.write(slave=dev.address, address=self.REG_SEGMENTS + i, value=0)
                # Спецсимволы
                if dev.device_type in (DeviceType.SPECIAL, DeviceType.SLIDER):
                    self.client.write(slave=dev.address, address=self.REG_SPECIAL, value=0)
                # Слайдер
                if dev.device_type == DeviceType.SLIDER:
                    self._write_float(dev.address, self.REG_SLIDER, 0.0)
            except:
                pass

    def _test_step(self):
        """Один шаг цикла теста (вызывается рекурсивно через after)"""
        if not self._test_active:
            return
        
        # === ЦИКЛ ТЕСТА ===
        if self._test_cycle == 0:
            # Шаг 0: Смена цвета
            self._set_color_all(self._current_color)
            self._log(f"Цикл {self._test_cycle + 1}: цвет = {self._current_color}")
            self._after_step(1)
            
        elif self._test_cycle == 1:
            # Шаг 1: Спецсимволы ВКЛ (только тип 2)
            devices = [d for d in self.devices if d.device_type == DeviceType.SPECIAL]
            if devices:
                self._log("Тест спецсимволов: ВКЛ")
                self._test_special_symbols(devices, direction="on", callback=lambda: self._after_step(2))
            else:
                self._after_step(2)
                
        elif self._test_cycle == 2:
            # Шаг 2: Сегменты индикатора ВКЛ (все устройства)
            self._log("Тест сегментов: ВКЛ")
            self._test_segments_all(direction="up", callback=lambda: self._after_step(3))
            
        elif self._test_cycle == 3:
            # Шаг 3: Слайдер ВКЛ (только тип 3)
            devices = [d for d in self.devices if d.device_type == DeviceType.SLIDER]
            if devices:
                self._log("Тест слайдера: ВКЛ (1→100)")
                self._test_slider_parallel(devices, direction="up", callback=lambda: self._after_step(4))
            else:
                self._after_step(4)
                
        elif self._test_cycle == 4:
            # Шаг 4: Шкала ВКЛ (только тип 3)
            devices = [d for d in self.devices if d.device_type == DeviceType.SLIDER]
            if devices:
                self._log("Тест шкалы: ВКЛ")
                self._test_scale_parallel(devices, direction="on", callback=lambda: self._after_step(5))
            else:
                self._after_step(5)
                
        elif self._test_cycle == 5:
            # Шаг 5: Сегменты индикатора ВЫКЛ (все устройства)
            self._log("Тест сегментов: ВЫКЛ")
            self._test_segments_all(direction="down", callback=lambda: self._after_step(6))
            
        elif self._test_cycle == 6:
            # Шаг 6: Слайдер ВЫКЛ (только тип 3)
            devices = [d for d in self.devices if d.device_type == DeviceType.SLIDER]
            if devices:
                self._log("Тест слайдера: ВЫКЛ (100→1)")
                self._test_slider_parallel(devices, direction="down", callback=lambda: self._after_step(7))
            else:
                self._after_step(7)
                
        elif self._test_cycle == 7:
            # Шаг 7: Шкала ВЫКЛ (только тип 3)
            devices = [d for d in self.devices if d.device_type == DeviceType.SLIDER]
            if devices:
                self._log("Тест шкалы: ВЫКЛ")
                self._test_scale_parallel(devices, direction="off", callback=lambda: self._after_step(8))
            else:
                self._after_step(8)
                
        elif self._test_cycle == 8:
            # Шаг 8: Спецсимволы ВЫКЛ (только тип 2)
            devices = [d for d in self.devices if d.device_type == DeviceType.SPECIAL]
            if devices:
                self._log("Тест спецсимволов: ВЫКЛ")
                self._test_special_symbols(devices, direction="off", callback=lambda: self._next_cycle())
            else:
                self._next_cycle()

    def _after_step(self, next_step: int):
        """Переход к следующему шагу с задержкой"""
        self._test_cycle = next_step
        self.after(self._step_delay_ms * 10, self._test_step)  # Небольшая пауза между шагами

    def _next_cycle(self):
        """Завершение цикла и переход к следующему"""
        self._test_cycle = 0
        self._current_color = 1 - self._current_color  # Переключение цвета
        self.cycle_label.config(text=f"Цикл: {self._test_cycle + 1}")
        self._log(f"✓ Цикл завершён. Пауза {self._cycle_delay_ms}мс...")
        self.after(self._cycle_delay_ms, self._test_step)

    # =========================================================
    # TEST PRIMITIVES
    # =========================================================

    def _set_color_all(self, color: int):
        """Установить цвет подсветки на всех устройствах"""
        for dev in self.devices:
            self.client.write(slave=dev.address, address=self.REG_COLOR, value=color)

    def _test_segments_all(self, direction: str, callback: Callable):
        """Запуск теста сегментов с динамическим basis"""
        if not self.devices:
            callback()
            return
        
        # 🔹 Находим максимальный basis для синхронизации шагов
        max_basis = max(dev.basis for dev in self.devices)
        
        if direction == "up":
            self._log(f"  Индикаторы: включение (0→{max_basis-1} ячейка)")
            self._segments_step_up(0, 0, max_basis, callback)
        else:
            self._log(f"  Индикаторы: выключение ({max_basis-1}→0 ячейка)")
            self._segments_step_down(max_basis - 1, 7, max_basis, callback)

    def _segments_step_up(self, cell: int, segment: int, max_basis: int, callback: Callable):
        """Включение сегментов с учётом basis каждого устройства"""
        if cell >= max_basis:
            callback()
            return
        if segment >= 8:
            self._segments_step_up(cell + 1, 0, max_basis, callback)
            return

        for dev in self.devices:
            # 🔹 Формируем ячейки под basis устройства
            cells = [0] * dev.basis
            # Предыдущие ячейки: полностью включены
            for prev in range(min(cell, dev.basis)):
                cells[prev] = 0xFF
            # Текущая ячейка: включаем сегменты 0..segment
            if cell < dev.basis:
                cells[cell] = (1 << (segment + 1)) - 1
            # Кодируем в регистры и пишем
            regs = self._cells_to_registers(cells)
            for i, reg_val in enumerate(regs):
                self.client.write(slave=dev.address, address=self.REG_SEGMENTS + i, value=reg_val)
        
        self.after(self._step_delay_ms, lambda: self._segments_step_up(cell, segment + 1, max_basis, callback))

    def _segments_step_down(self, cell: int, segment: int, max_basis: int, callback: Callable):
        """Выключение сегментов (обратный порядок)"""
        if cell < 0:
            callback()
            return
        if segment < 0:
            self._segments_step_down(cell - 1, 7, max_basis, callback)
            return

        for dev in self.devices:
            cells = [0] * dev.basis
            for prev in range(min(cell, dev.basis)):
                cells[prev] = 0xFF
            if cell < dev.basis:
                cells[cell] = (1 << segment) - 1  # сегменты 0..segment-1 включены
            regs = self._cells_to_registers(cells)
            for i, reg_val in enumerate(regs):
                self.client.write(slave=dev.address, address=self.REG_SEGMENTS + i, value=reg_val)
        
        self.after(self._step_delay_ms, lambda: self._segments_step_down(cell, segment - 1, max_basis, callback))

    def _segments_step(self, cell: int, segment: int, num_cells: int, direction: str, callback: Callable):
        """Рекурсивный шаг теста сегментов"""
        if cell >= num_cells:
            callback()
            return
        
        if segment >= 8:
            # Переход к следующей ячейке
            self._segments_step(cell + 1, 0, num_cells, direction, callback)
            return
        
        # Формирование маски
        all_cells = [0] * num_cells
        
        # Предыдущие ячейки: все сегменты включены
        for prev in range(cell):
            all_cells[prev] = 0xFF
        
        # Текущая ячейка
        if direction == "up":
            mask = (1 << (segment + 1)) - 1  # Включаем от 0 до segment
        else:
            mask = (1 << segment) - 1  # Включаем от 0 до segment-1 (выключаем segment)
        all_cells[cell] = mask
        
        # Запись на все устройства
        reg1, reg2 = self._encode_four_numbers(*all_cells)
        for dev in self.devices:
            self.client.write(slave=dev.address, address=self.REG_SEGMENTS, value=reg1)
            self.client.write(slave=dev.address, address=self.REG_SEGMENTS + 1, value=reg2)
        
        # Следующий сегмент
        self.after(self._step_delay_ms, 
                  lambda: self._segments_step(cell, segment + 1, num_cells, direction, callback))

    def _test_special_symbols(self, devices: List[DiscoveredDevice], direction: str, callback: Callable):
        """
        Тест специальных символов (накопительное включение/выключение)
        :param devices: список устройств типа SPECIAL
        :param direction: "on" или "off"
        :param callback: по завершении
        """
        # Битовые маски сегментов спец. знака
        segments = [
            (0x0400, 'a'), (0x0800, 'b'), (0x0100, 'c'), (0x0200, 'd'),
            (0x4000, 'e'), (0x8000, 'f'), (0x1000, 'g'), (0x2000, 'h'),
            (0x0004, 'i'), (0x0008, 'j'), (0x0001, 'k'), (0x0002, 'l'), (0x0010, 'm')
        ]
        
        if direction == "on":
            self._special_step_on(devices, segments, 0, 0, callback)
        else:
            # Начинаем с полной маски
            full_mask = sum(mask for mask, _ in segments)
            self._special_step_off(devices, list(reversed(segments)), 0, full_mask, callback)

    def _special_step_on(self, devices, segments, idx: int, accumulated: int, callback: Callable):
        if idx >= len(segments):
            callback()
            return
        
        mask, name = segments[idx]
        accumulated |= mask
        
        for dev in devices:
            self.client.write(slave=dev.address, address=self.REG_SPECIAL, value=accumulated)
        
        self._log(f"  Спецсимвол {name}: включён (всего: {bin(accumulated).count('1')})")
        self.after(self._step_delay_ms, 
                  lambda: self._special_step_on(devices, segments, idx + 1, accumulated, callback))

    def _special_step_off(self, devices, segments, idx: int, accumulated: int, callback: Callable):
        if idx >= len(segments):
            # Финальный сброс
            for dev in devices:
                self.client.write(slave=dev.address, address=self.REG_SPECIAL, value=0)
            callback()
            return
        
        mask, name = segments[idx]
        accumulated &= ~mask
        
        for dev in devices:
            self.client.write(slave=dev.address, address=self.REG_SPECIAL, value=accumulated)
        
        self._log(f"  Спецсимвол {name}: выключен (осталось: {bin(accumulated).count('1')})")
        self.after(self._step_delay_ms,
                  lambda: self._special_step_off(devices, segments, idx + 1, accumulated, callback))

    def _test_slider_parallel(self, devices: List[DiscoveredDevice], direction: str, callback: Callable):
        """
        Параллельный тест слайдера (плавное изменение 1→100 или 100→1)
        """
        values = range(1, 101) if direction == "up" else range(100, 0, -1)
        self._slider_step(devices, list(values), 0, callback)

    def _slider_step(self, devices, values: list, idx: int, callback: Callable):
        if idx >= len(values):
            callback()
            return
        
        val = values[idx]
        reg1, reg2 = self._float_to_registers(float(val))
        
        for dev in devices:
            self.client.write(slave=dev.address, address=self.REG_SLIDER, values=[reg1, reg2])
        
        self._log(f"  Слайдер: значение = {val}")
        self.after(self._step_delay_ms,
                  lambda: self._slider_step(devices, values, idx + 1, callback))

    def _test_scale_parallel(self, devices: List[DiscoveredDevice], direction: str, callback: Callable):
        """
        Параллельный тест шкалы (64 бита, 4 регистра)
        """
        total_bits = 64
        if direction == "on":
            self._scale_step_on(devices, 0, total_bits, callback)
        else:
            full_mask = (1 << total_bits) - 1
            self._scale_step_off(devices, total_bits - 1, full_mask, callback)

    def _scale_step_on(self, devices, bit: int, total: int, callback: Callable):
        if bit >= total:
            callback()
            return
        
        mask = (1 << (bit + 1)) - 1  # Биты 0..bit включены
        self._write_scale_mask(devices, mask)
        self._log(f"  Шкала: бит {bit + 1}/{total} включён")
        self.after(self._step_delay_ms,
                  lambda: self._scale_step_on(devices, bit + 1, total, callback))

    def _scale_step_off(self, devices, bit: int, mask: int, callback: Callable):
        if bit < 0:
            # Финальный сброс
            for dev in devices:
                self.client.write(slave=dev.address, address=self.REG_SCALE_BASE, value=0)
                self.client.write(slave=dev.address, address=self.REG_SCALE_BASE + 1, value=0)
                self.client.write(slave=dev.address, address=self.REG_SCALE_BASE + 2, value=0)
                self.client.write(slave=dev.address, address=self.REG_SCALE_BASE + 3, value=0)
            callback()
            return
        
        mask &= ~(1 << bit)  # Выключаем текущий бит
        self._write_scale_mask(devices, mask)
        self._log(f"  Шкала: бит {bit + 1} выключен")
        self.after(self._step_delay_ms,
                  lambda: self._scale_step_off(devices, bit - 1, mask, callback))

    def _write_scale_mask(self, devices: List[DiscoveredDevice], mask: int):
        """Запись 64-битной маски шкалы (4 регистра)"""
        regs = [
            self._swap_endian16((mask >> 0) & 0xFFFF),
            self._swap_endian16((mask >> 16) & 0xFFFF),
            self._swap_endian16((mask >> 32) & 0xFFFF),
            self._swap_endian16((mask >> 48) & 0xFFFF)
        ]
        for dev in devices:
            self.client.write(slave=dev.address, address=self.REG_SCALE_BASE, values=regs)

    # =========================================================
    # CODECS
    # =========================================================

    def _float_to_registers(self, fval: float) -> tuple:
        """Float32 → два 16-битных регистра (Big-Endian)"""
        import struct
        packed = struct.pack('>f', fval)
        reg1 = (packed[0] << 8) | packed[1]
        reg2 = (packed[2] << 8) | packed[3]
        return reg1, reg2

    def _encode_four_numbers(self, n1: int, n2: int, n3: int, n4: int) -> tuple:
        """4 байта → два 16-битных регистра"""
        reg1 = (n1 << 8) | n2
        reg2 = (n3 << 8) | n4
        return reg1, reg2

    def _swap_endian16(self, val: int) -> int:
        """Swap byte order для 16-битного значения"""
        return ((val & 0xFF) << 8) | ((val >> 8) & 0xFF)

    # =========================================================
    # CLEANUP
    # =========================================================

    def destroy(self):
        """Очистка при закрытии виджета"""
        if self._test_active:
            self._stop_test()
        super().destroy()