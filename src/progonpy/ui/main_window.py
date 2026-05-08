# src/progonpy/ui/main_window.py
from __future__ import annotations

import serial.tools.list_ports
from PySide2.QtCore import Qt, QThreadPool
from PySide2.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from progonpy.domain.models import SerialConfig
from progonpy.services.discovery import DeviceDiscoveryService
from progonpy.workers.tasks import Task
from progonpy.ui.test_panel import TestPanel

class MainWindow(QMainWindow):
    def __init__(self, app_service) -> None:
        super().__init__()
        self.app_service = app_service
        self.pool = QThreadPool.globalInstance()
        self.setWindowTitle("ProgonPy — Modbus Test Bench")
        self.resize(1000, 700)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        # 1. Настройки подключения
        form = QFormLayout()
        self.port_box = QComboBox()
        self.port_box.addItems([p.device for p in serial.tools.list_ports.comports()])
        self.baud_box = QComboBox()
        self.baud_box.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.stopbits_box = QComboBox()
        self.stopbits_box.addItems(["1", "1.5", "2"])
        form.addRow("COM-порт", self.port_box)
        form.addRow("Скорость", self.baud_box)
        form.addRow("Стоп-биты", self.stopbits_box)
        layout.addLayout(form)

        # 2. Кнопки управления
        btns = QHBoxLayout()
        self.connect_btn = QPushButton("Подключить")
        self.scan_btn = QPushButton("Сканировать")
        btns.addWidget(self.connect_btn)
        btns.addWidget(self.scan_btn)
        layout.addLayout(btns)

        # 3. Диапазон сканирования
        range_line = QHBoxLayout()
        self.start_spin = QSpinBox()
        self.start_spin.setRange(1, 247)
        self.start_spin.setValue(1)
        self.end_spin = QSpinBox()
        self.end_spin.setRange(1, 247)
        self.end_spin.setValue(50)
        range_line.addWidget(QLabel("ID от"))
        range_line.addWidget(self.start_spin)
        range_line.addWidget(QLabel("до"))
        range_line.addWidget(self.end_spin)
        layout.addLayout(range_line)

        # 4. Список устройств
        self.devices_list = QListWidget()

        # === ИСПРАВЛЕНИЕ: Правильное создание вкладок ===
        self.tabs = QTabWidget()
        
        # Вкладка 1: Список устройств
        devices_tab = QWidget()
        devices_layout = QVBoxLayout(devices_tab)
        devices_layout.addWidget(self.devices_list)
        self.tabs.addTab(devices_tab, "📋 Устройства")
        
        # Вкладка 2: Панель тестирования
        self.test_panel = TestPanel(self.app_service.device_test)
        self.tabs.addTab(self.test_panel, "🧪 Тест")
        
        # Добавляем виджет вкладок в основное окно
        layout.addWidget(self.tabs)

        # 5. Подключение сигналов
        self.connect_btn.clicked.connect(self.on_connect)
        self.scan_btn.clicked.connect(self.on_scan)
        self.devices_list.currentItemChanged.connect(self._on_device_selected)
        
        self._load_settings()

    def _on_device_selected(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        """При клике на устройство передаём его адрес в тест-панель"""
        if current:
            device = current.data(Qt.UserRole)
            if device:
                self.test_panel.set_device(device.address)

    def _load_settings(self) -> None:
        config = self.app_service.load_settings()
        if not config:
            return
        idx = self.port_box.findText(config.port)
        if idx >= 0:
            self.port_box.setCurrentIndex(idx)
        self.baud_box.setCurrentText(str(config.baudrate))
        self.stopbits_box.setCurrentText(str(config.stopbits))

    def current_config(self) -> SerialConfig:
        return SerialConfig(
            port=self.port_box.currentText(),
            baudrate=int(self.baud_box.currentText()),
            stopbits=float(self.stopbits_box.currentText()),
        )

    def on_connect(self) -> None:
        config = self.current_config()
        try:
            self.app_service.connect(config)
            self.app_service.save_settings(config)
            QMessageBox.information(self, "ОК", "Подключение установлено")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def on_scan(self) -> None:
        start = self.start_spin.value()
        end = self.end_spin.value()
        task = Task(lambda: DeviceDiscoveryService(self.app_service.modbus).scan(start, end))
        task.signals.finished.connect(self._render_devices)
        task.signals.failed.connect(lambda e: QMessageBox.critical(self, "Ошибка сканирования", e))
        self.pool.start(task)

    def _render_devices(self, devices) -> None:
        self.devices_list.clear()
        for device in devices:
            item = QListWidgetItem(f"ID {device.address}")
            item.setData(Qt.UserRole, device)
            self.devices_list.addItem(item)
        QMessageBox.information(self, "Сканирование", f"Найдено устройств: {len(devices)}")