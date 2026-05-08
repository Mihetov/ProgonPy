from __future__ import annotations

import struct

import serial

from progonpy.domain.models import SerialConfig


class ModbusRtuClient:
    def __init__(self) -> None:
        self.serial: serial.Serial | None = None

    def connect(self, config: SerialConfig) -> bool:
        stopbits_map = {1: serial.STOPBITS_ONE, 1.5: serial.STOPBITS_ONE_POINT_FIVE, 2: serial.STOPBITS_TWO}
        self.serial = serial.Serial(
            port=config.port,
            baudrate=config.baudrate,
            parity=config.parity,
            stopbits=stopbits_map.get(config.stopbits, serial.STOPBITS_ONE),
            bytesize=config.bytesize,
            timeout=config.timeout,
        )
        return True

    def disconnect(self) -> None:
        if self.serial and self.serial.is_open:
            self.serial.close()

    @staticmethod
    def _crc(data: list[int]) -> int:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
        return crc

    def _request(self, frame: list[int]) -> list[int] | None:
        if not self.serial or not self.serial.is_open:
            return None
        crc = self._crc(frame)
        packet = bytes(frame + [crc & 0xFF, (crc >> 8) & 0xFF])
        self.serial.write(packet)
        self.serial.flush()
        raw = self.serial.read(256)
        if len(raw) < 5:
            return None
        return list(raw)

    def read_registers(self, address: int, register: int, count: int) -> list[int] | None:
        resp = self._request([address, 0x03, register >> 8, register & 0xFF, count >> 8, count & 0xFF])
        if not resp or resp[1] != 0x03:
            return None
        values = []
        for i in range(count):
            values.append((resp[3 + i * 2] << 8) | resp[4 + i * 2])
        return values

    def write_register(self, address: int, register: int, value: int) -> bool:
        resp = self._request([address, 0x06, register >> 8, register & 0xFF, value >> 8, value & 0xFF])
        return bool(resp and resp[1] == 0x06)

    def write_registers(self, address: int, register: int, values: list[int]) -> bool:
        quantity = len(values)
        frame = [address, 0x10, register >> 8, register & 0xFF, quantity >> 8, quantity & 0xFF, quantity * 2]
        for value in values:
            frame.extend([value >> 8, value & 0xFF])
        resp = self._request(frame)
        return bool(resp and resp[1] == 0x10)


def float_to_registers(value: float) -> tuple[int, int]:
    packed = struct.pack(">f", value)
    return ((packed[0] << 8) | packed[1], (packed[2] << 8) | packed[3])
