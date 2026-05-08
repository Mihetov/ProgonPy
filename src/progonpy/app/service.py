from __future__ import annotations

from progonpy.domain.models import SerialConfig
from progonpy.infra.modbus_rtu import ModbusRtuClient
from progonpy.infra.settings import SettingsRepository
from progonpy.services.device_test import DeviceTestService

class ApplicationService:
    def __init__(self) -> None:
        self.modbus = ModbusRtuClient()
        self.settings = SettingsRepository()
        self.device_test = DeviceTestService(self.modbus)
    def start_device_test(self, address: int, on_progress=None, on_finished=None):
        """Запустить тест устройства (асинхронно)"""
        # Здесь можно обернуть в QRunnable или вернуть Task для UI
        return self.device_test.run_full_test(address)

    def connect(self, config: SerialConfig) -> None:
        self.modbus.connect(config)

    def load_settings(self):
        return self.settings.load_serial_config()

    def save_settings(self, config: SerialConfig) -> None:
        self.settings.save_serial_config(config)
