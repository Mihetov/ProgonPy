from __future__ import annotations

from progonpy.domain.models import SerialConfig
from progonpy.infra.modbus_rtu import ModbusRtuClient
from progonpy.infra.settings import SettingsRepository


class ApplicationService:
    def __init__(self) -> None:
        self.modbus = ModbusRtuClient()
        self.settings = SettingsRepository()

    def connect(self, config: SerialConfig) -> None:
        self.modbus.connect(config)

    def load_settings(self):
        return self.settings.load_serial_config()

    def save_settings(self, config: SerialConfig) -> None:
        self.settings.save_serial_config(config)
