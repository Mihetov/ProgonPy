from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from progonpy.domain.models import Device
from progonpy.domain.protocols import ModbusPort
from progonpy.infra.modbus_rtu import float_to_registers


class DeviceTestService:
    def __init__(self, modbus: ModbusPort) -> None:
        self.modbus = modbus

    def set_color_parallel(self, devices: list[Device], color: int) -> None:
        with ThreadPoolExecutor(max_workers=max(1, len(devices))) as pool:
            for d in devices:
                pool.submit(self.modbus.write_register, d.address, 0xE002, color)

    def run_slider_parallel(self, devices: list[Device], start: int, end: int, step: int) -> None:
        for value in range(start, end, step):
            reg1, reg2 = float_to_registers(float(value))
            with ThreadPoolExecutor(max_workers=max(1, len(devices))) as pool:
                for d in devices:
                    pool.submit(self.modbus.write_registers, d.address, 0xC100, [reg1, reg2])
