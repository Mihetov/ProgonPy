# src/progonpy/domain/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class DeviceType(Enum):
    """Типы поддерживаемых устройств"""
    BASIC = 1       # Обычное устройство (только цифры)
    SPECIAL = 2     # Со спецсимволами
    SLIDER = 3      # Со слайдером и шкалой


@dataclass
class SerialConfig:
    """Конфигурация последовательного порта"""
    port: str
    baudrate: int = 9600
    parity: str = 'N'      # 'N', 'E', 'O'
    stopbits: float = 1.0  # 1, 1.5, 2
    bytesize: int = 8
    timeout: float = 0.05
    
    def __post_init__(self):
        # Нормализация параметров для совместимости с pyserial
        if self.parity.upper() == 'NONE':
            self.parity = 'N'
        elif self.parity.upper() == 'EVEN':
            self.parity = 'E'
        elif self.parity.upper() == 'ODD':
            self.parity = 'O'


@dataclass
class Device:
    """Модель обнаруженного устройства"""
    address: int
    device_type: DeviceType = DeviceType.BASIC
    name: Optional[str] = None
    
    def __str__(self) -> str:
        type_names = {
            DeviceType.BASIC: "Базовое",
            DeviceType.SPECIAL: "Спецсимволы", 
            DeviceType.SLIDER: "Слайдер"
        }
        return f"Устройство #{self.address} ({type_names.get(self.device_type, '?')})"


# ============================================
# Классы для системы тестирования (НОВЫЕ)
# ============================================

class TestStatus(Enum):
    """Статус выполнения шага теста"""
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass
class TestStep:
    """Описание одного шага теста"""
    name: str
    register: int
    write_value: Optional[int] = None
    expected_read: Optional[int] = None
    count: int = 1
    description: str = ""


@dataclass
class TestResult:
    """Результат выполнения одного шага теста"""
    step: TestStep
    status: TestStatus
    actual_value: Optional[int] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    
    @property
    def is_success(self) -> bool:
        return self.status == TestStatus.SUCCESS


@dataclass
class TestReport:
    """Полный отчёт по тесту устройства"""
    device_address: int
    test_name: str
    steps: list[TestResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    
    @property
    def is_success(self) -> bool:
        return all(step.is_success for step in self.steps)
    
    @property
    def duration_ms(self) -> float:
        return self.end_time - self.start_time


# ============================================
# Вспомогательные функции
# ============================================

def float_to_registers(value: float) -> tuple[int, int]:
    """
    Преобразует float в два 16-битных регистра (IEEE 754, Big-Endian)
    Возвращает (старшее слово, младшее слово)
    """
    import struct
    packed = struct.pack(">f", value)  # Big-endian float
    reg1 = (packed[0] << 8) | packed[1]  # Старший байт + младший байт = слово 1
    reg2 = (packed[2] << 8) | packed[3]  # Слово 2
    return reg1, reg2


def registers_to_float(reg1: int, reg2: int) -> float:
    """
    Обратное преобразование: два 16-битных регистра -> float
    """
    import struct
    packed = bytes([
        (reg1 >> 8) & 0xFF, reg1 & 0xFF,
        (reg2 >> 8) & 0xFF, reg2 & 0xFF
    ])
    return struct.unpack(">f", packed)[0]