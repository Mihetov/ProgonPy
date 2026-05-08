# src/progonpy/services/device_test.py
from __future__ import annotations

import time
import struct
import logging
from typing import Optional, Callable

from progonpy.domain.models import (
    TestStep, TestResult, TestReport, TestStatus,
    float_to_registers
)
from progonpy.domain.protocols import DeviceTestPort

logger = logging.getLogger(__name__)


class DeviceTestService:
    """Сервис для комплексного тестирования Modbus-устройств"""
    
    # Регистры согласно документации устройства
    REG_ID = 0xF000          # R: адрес устройства
    REG_DISPLAY = 0x0000     # RW: 8-сегментный индикатор (2 регистра)
    REG_SPECIAL = 0xC000     # RW: спецсимволы (13 бит)
    REG_SLIDER = 0xC100      # W: слайдер (float, 2 регистра)
    REG_SCALE = 0xC000       # W: шкала (64 бита, 4 регистра)
    REG_COLOR = 0xE002       # W: цвет подсветки
    
    # Битовые маски для сегментов индикатора (ячейка 0)
    SEGMENT_MASKS = [
        0x0080, 0x0040, 0x0020, 0x0010,  # a, b, c, d
        0x0008, 0x0004, 0x0002, 0x0001,  # e, f, g, dp
    ]
    SEGMENT_NAMES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'dp']
    
    # Маски спецсимволов (бит -> имя)
    SPECIAL_SYMBOLS = [
        (0x0400, 'a'), (0x0800, 'b'), (0x0100, 'c'), (0x0200, 'd'),
        (0x4000, 'e'), (0x8000, 'f'), (0x1000, 'g'), (0x2000, 'h'),
        (0x0004, 'i'), (0x0008, 'j'), (0x0001, 'k'), (0x0002, 'l'),
        (0x0010, 'm'),
    ]
    
    def __init__(self, modbus: DeviceTestPort):
        self.modbus = modbus
        self._on_progress: Optional[Callable[[str, float], None]] = None
    
    def set_progress_callback(self, callback: Callable[[str, float], None]) -> None:
        """Установить коллбэк для обновления прогресса в UI"""
        self._on_progress = callback
    
    def _progress(self, message: str, percent: float) -> None:
        if self._on_progress:
            self._on_progress(message, percent)
        logger.debug(f"[{percent:.0f}%] {message}")
    
    def _read_safe(self, address: int, register: int, count: int = 1) -> Optional[list[int]]:
        """Безопасное чтение с логированием"""
        result = self.modbus.read_registers(address, register, count)
        if result is None:
            logger.warning(f"Read failed: addr={address}, reg=0x{register:04X}")
        return result
    
    def _write_safe(self, address: int, register: int, value: int) -> bool:
        """Безопасная запись с логированием"""
        result = self.modbus.write_register(address, register, value)
        if not result:
            logger.warning(f"Write failed: addr={address}, reg=0x{register:04X}, val=0x{value:04X}")
        return result
    
    def test_id_register(self, address: int) -> TestResult:
        """Тест регистра идентификации (0xF000)"""
        step = TestStep(
            name="Проверка ID",
            register=self.REG_ID,
            description="Чтение адреса устройства"
        )
        start = time.time()
        
        try:
            resp = self._read_safe(address, self.REG_ID, 1)
            duration = (time.time() - start) * 1000
            
            if resp and resp[0] == address:
                return TestResult(step, TestStatus.SUCCESS, resp[0], duration_ms=duration)
            elif resp:
                return TestResult(
                    step, TestStatus.FAILED, resp[0],
                    error=f"Неверный адрес: ожидался {address}, получен {resp[0]}",
                    duration_ms=duration
                )
            else:
                return TestResult(step, TestStatus.FAILED, error="Нет ответа", duration_ms=duration)
                
        except Exception as e:
            return TestResult(step, TestStatus.FAILED, error=f"{type(e).__name__}: {e}")
    
    def test_display_segments(self, address: int, cell: int = 0) -> list[TestResult]:
        """Поочередное тестирование сегментов 8-сегментного индикатора"""
        results = []
        base_reg = self.REG_DISPLAY + cell // 2  # 2 ячейки на регистр
        
        for seg_idx, mask in enumerate(self.SEGMENT_MASKS):
            step = TestStep(
                name=f"Сегмент {self.SEGMENT_NAMES[seg_idx]} (ячейка {cell+1})",
                register=base_reg,
                write_value=mask,
                description=f"Включение сегмента {self.SEGMENT_NAMES[seg_idx]}"
            )
            start = time.time()
            
            try:
                # Записываем маску
                if self._write_safe(address, base_reg, mask):
                    time.sleep(0.1)  # Даем устройству время отреагировать
                    # Читаем обратно для подтверждения
                    resp = self._read_safe(address, base_reg, 1)
                    duration = (time.time() - start) * 1000
                    
                    if resp and resp[0] == mask:
                        results.append(TestResult(step, TestStatus.SUCCESS, resp[0], duration_ms=duration))
                    else:
                        results.append(TestResult(
                            step, TestStatus.FAILED, resp[0] if resp else None,
                            error="Чтение не подтверждает запись", duration_ms=duration
                        ))
                else:
                    results.append(TestResult(step, TestStatus.FAILED, error="Ошибка записи"))
                    
            except Exception as e:
                results.append(TestResult(step, TestStatus.FAILED, error=f"{type(e).__name__}: {e}"))
            
            self._progress(f"Тест сегмента {self.SEGMENT_NAMES[seg_idx]}", 
                          (seg_idx + 1) / len(self.SEGMENT_MASKS) * 100)
        
        # Выключаем всё после теста
        self._write_safe(address, base_reg, 0)
        return results
    
    def test_special_symbols(self, address: int) -> list[TestResult]:
        """Тест специальных символов с накопительным включением"""
        results = []
        accumulated = 0
        
        for mask, name in self.SPECIAL_SYMBOLS:
            step = TestStep(
                name=f"Спецсимвол '{name}'",
                register=self.REG_SPECIAL,
                write_value=mask,
                description=f"Включение спецсимвола {name}"
            )
            start = time.time()
            
            try:
                accumulated |= mask  # Накопительное включение
                if self._write_safe(address, self.REG_SPECIAL, accumulated):
                    time.sleep(0.05)
                    resp = self._read_safe(address, self.REG_SPECIAL, 1)
                    duration = (time.time() - start) * 1000
                    
                    # Проверяем, что бит установлен
                    if resp and (resp[0] & mask):
                        results.append(TestResult(step, TestStatus.SUCCESS, resp[0], duration_ms=duration))
                    else:
                        results.append(TestResult(
                            step, TestStatus.FAILED, resp[0] if resp else None,
                            error=f"Бит 0x{mask:04X} не установлен", duration_ms=duration
                        ))
                else:
                    results.append(TestResult(step, TestStatus.FAILED, error="Ошибка записи"))
                    
            except Exception as e:
                results.append(TestResult(step, TestStatus.FAILED, error=f"{type(e).__name__}: {e}"))
            
            self._progress(f"Спецсимвол '{name}'", 
                          self.SPECIAL_SYMBOLS.index((mask, name)) / len(self.SPECIAL_SYMBOLS) * 100)
        
        # Выключаем всё
        self._write_safe(address, self.REG_SPECIAL, 0)
        return results
    
    def test_slider(self, address: int, test_values: list[float] = None) -> list[TestResult]:
        """Тест слайдера (запись float в 0xC100-0xC101)"""
        if test_values is None:
            test_values = [0.0, 25.0, 50.0, 75.0, 100.0]
        
        results = []
        
        for value in test_values:
            step = TestStep(
                name=f"Слайдер = {value}",
                register=self.REG_SLIDER,
                write_value=int(value),  # Для отображения
                description=f"Запись float {value} в слайдер"
            )
            start = time.time()
            
            try:
                reg1, reg2 = float_to_registers(value)
                if self.modbus.write_registers(address, self.REG_SLIDER, [reg1, reg2]):
                    time.sleep(0.1)
                    # Читаем обратно (опционально, не все устройства поддерживают чтение слайдера)
                    resp = self._read_safe(address, self.REG_SLIDER, 2)
                    duration = (time.time() - start) * 1000
                    
                    results.append(TestResult(step, TestStatus.SUCCESS, duration_ms=duration))
                else:
                    results.append(TestResult(step, TestStatus.FAILED, error="Ошибка записи float"))
                    
            except Exception as e:
                results.append(TestResult(step, TestStatus.FAILED, error=f"{type(e).__name__}: {e}"))
            
            self._progress(f"Слайдер {value}", test_values.index(value) / len(test_values) * 100)
        
        return results
    
    def test_color(self, address: int, colors: list[int] = None) -> list[TestResult]:
        """Тест цвета подсветки (0 = синий, 1 = красный)"""
        if colors is None:
            colors = [0, 1]
        
        results = []
        
        for color in colors:
            step = TestStep(
                name=f"Цвет = {'синий' if color == 0 else 'красный'}",
                register=self.REG_COLOR,
                write_value=color,
                description=f"Установка цвета подсветки"
            )
            start = time.time()
            
            try:
                if self._write_safe(address, self.REG_COLOR, color):
                    time.sleep(0.1)
                    duration = (time.time() - start) * 1000
                    results.append(TestResult(step, TestStatus.SUCCESS, duration_ms=duration))
                else:
                    results.append(TestResult(step, TestStatus.FAILED, error="Ошибка записи цвета"))
                    
            except Exception as e:
                results.append(TestResult(step, TestStatus.FAILED, error=f"{type(e).__name__}: {e}"))
        
        return results
    
    def run_full_test(self, address: int) -> TestReport:
        """Запуск полного цикла тестирования устройства"""
        report = TestReport(
            device_address=address,
            test_name="Полный тест устройства",
            start_time=time.time() * 1000
        )
        
        self._progress("Начало теста", 0)
        
        # 1. Проверка ID (обязательная)
        self._progress("Проверка ID", 5)
        id_result = self.test_id_register(address)
        report.steps.append(id_result)
        
        if id_result.status != TestStatus.SUCCESS:
            self._progress("Тест прерван: устройство не отвечает", 100)
            report.end_time = time.time() * 1000
            return report
        
        # 2. Тест сегментов дисплея
        self._progress("Тест сегментов", 20)
        report.steps.extend(self.test_display_segments(address))
        
        # 3. Тест спецсимволов
        self._progress("Тест спецсимволов", 50)
        report.steps.extend(self.test_special_symbols(address))
        
        # 4. Тест слайдера
        self._progress("Тест слайдера", 75)
        report.steps.extend(self.test_slider(address))
        
        # 5. Тест цвета
        self._progress("Тест цвета", 90)
        report.steps.extend(self.test_color(address))
        
        # Завершение
        self._progress("Тест завершён", 100)
        report.end_time = time.time() * 1000
        
        return report