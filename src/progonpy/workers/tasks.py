from __future__ import annotations

from typing import Callable, Generic, TypeVar

from PySide6.QtCore import QObject, QRunnable, Signal

T = TypeVar("T")


class TaskSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class Task(QRunnable, Generic[T]):
    def __init__(self, fn: Callable[[], T]) -> None:
        super().__init__()
        self.fn = fn
        self.signals = TaskSignals()

    def run(self) -> None:
        try:
            result = self.fn()
            self.signals.finished.emit(result)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
