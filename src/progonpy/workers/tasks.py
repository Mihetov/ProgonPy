# src/progonpy/workers/tasks.py
from __future__ import annotations

import logging
from typing import Callable, Optional, Any

from PySide2.QtCore import QRunnable, QObject, Signal, Slot

logger = logging.getLogger(__name__)


# ============================================
# Класс Task — для сканирования и других задач
# ============================================

class TaskSignals(QObject):
    """Сигналы для обновления UI из фоновой задачи"""
    finished = Signal(object)  # результат
    failed = Signal(str)       # сообщение об ошибке
    progress = Signal(str, int)  # опционально: сообщение, процент


class Task(QRunnable):
    """
    Универсальная фоновая задача для выполнения любой функции.
    
    Пример использования:
        task = Task(lambda: heavy_function(arg1, arg2))
        task.signals.finished.connect(on_result)
        task.signals.failed.connect(on_error)
        QThreadPool.globalInstance().start(task)
    """
    
    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = TaskSignals()
        self._is_cancelled = False
    
    def cancel(self) -> None:
        """Запросить отмену задачи (флаг, не принудительная остановка)"""
        self._is_cancelled = True
    
    @Slot()
    def run(self) -> None:
        """Выполнение задачи в фоновом потоке"""
        if self._is_cancelled:
            return
            
        try:
            logger.debug(f"Task started: {self.fn.__name__ if hasattr(self.fn, '__name__') else '<lambda>'}")
            result = self.fn(*self.args, **self.kwargs)
            
            if not self._is_cancelled:
                self.signals.finished.emit(result)
                
        except Exception as e:
            logger.error(f"Task failed: {e}", exc_info=True)
            if not self._is_cancelled:
                self.signals.failed.emit(f"{type(e).__name__}: {e}")


# ============================================
# Класс TestTask — для тестирования устройств
# ============================================

class TestSignals(QObject):
    """Специфичные сигналы для процесса тестирования"""
    progress = Signal(str, float)  # message, percent (0-100)
    step_result = Signal(object)   # TestResult
    finished = Signal(object)      # TestReport
    error = Signal(str)            # error_message


class TestTask(QRunnable):
    """
    Фоновая задача для запуска полного теста устройства.
    
    Использует DeviceTestService для выполнения пошаговой проверки.
    """
    
    def __init__(self, test_service, address: int):
        super().__init__()
        self.test_service = test_service
        self.address = address
        self.signals = TestSignals()
        self._is_cancelled = False
    
    def cancel(self) -> None:
        """Остановить выполнение теста"""
        self._is_cancelled = True
    
    @Slot()
    def run(self) -> None:
        """Запуск теста в фоновом потоке"""
        try:
            # Подключаем коллбэк для обновления прогресса
            def on_progress(msg: str, pct: float):
                if not self._is_cancelled:
                    self.signals.progress.emit(msg, pct)
            
            self.test_service.set_progress_callback(on_progress)
            
            # Запускаем тест
            report = self.test_service.run_full_test(self.address)
            
            if not self._is_cancelled:
                self.signals.finished.emit(report)
                
        except Exception as e:
            logger.error(f"TestTask failed: {e}", exc_info=True)
            if not self._is_cancelled:
                self.signals.error.emit(f"{type(e).__name__}: {e}")