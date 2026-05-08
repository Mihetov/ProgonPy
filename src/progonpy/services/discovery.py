from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from progonpy.domain.models import Device, DeviceType
from progonpy.domain.protocols import ModbusPort


class DeviceDiscoveryService:
    def __init__(self, modbus: ModbusPort) -> None:
        self.modbus = modbus

    def scan(self, start: int = 1, end: int = 247, workers: int = 16) -> list[Device]:
        found: list[Device] = []

        def probe(addr: int) -> Device | None:
            response = self.modbus.read_registers(addr, 0xF000, 1)
            if response and response[0] == addr:
                return Device(address=addr, device_type=DeviceType.BASIC)
            return None

        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_map = {pool.submit(probe, addr): addr for addr in range(start, end + 1)}
            for future in as_completed(future_map):
                device = future.result()
                if device:
                    found.append(device)

        return sorted(found, key=lambda d: d.address)
