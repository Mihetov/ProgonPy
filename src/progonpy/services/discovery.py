# src/progonpy/services/discovery.py
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from progonpy.domain.models import Device, DeviceType
from progonpy.domain.protocols import ModbusPort

logger = logging.getLogger(__name__)

class DeviceDiscoveryService:
    def __init__(self, modbus: ModbusPort) -> None:
        self.modbus = modbus

    def scan(self, start: int = 1, end: int = 247, workers: int = 1) -> list[Device]:
        found: list[Device] = []
        logger.info(f"Starting device scan from {start} to {end} with {workers} workers...")

        def probe(addr: int) -> Device | None:
            try:
                response = self.modbus.read_registers(addr, 0xF000, 1)
                if response and response[0] == addr:
                    logger.debug(f"Device found at address {addr}")
                    return Device(address=addr, device_type=DeviceType.BASIC)
            except Exception as e:
                logger.error(f"Error probing address {addr}: {e}")
            return None

        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_map = {pool.submit(probe, addr): addr for addr in range(start, end + 1)}
            for future in as_completed(future_map):
                device = future.result()
                if device:
                    found.append(device)
        
        logger.info(f"Scan completed. Found {len(found)} devices.")
        return sorted(found, key=lambda d: d.address)