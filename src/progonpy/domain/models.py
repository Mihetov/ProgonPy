from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DeviceType(Enum):
    BASIC = 1
    SPECIAL = 2
    SLIDER = 3


@dataclass(frozen=True)
class SerialConfig:
    port: str
    baudrate: int = 9600
    stopbits: float = 1
    parity: str = "N"
    bytesize: int = 8
    timeout: float = 1.0


@dataclass
class Device:
    address: int
    device_type: DeviceType = DeviceType.BASIC
    meta: dict[str, str] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return f"Устройство #{self.address} ({self.device_type.name})"
