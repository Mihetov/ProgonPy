# src/progonpy/ui/test_panel.py
from __future__ import annotations
from PySide2.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QProgressBar, QTextEdit, QGroupBox
)
from PySide2.QtCore import Qt, Slot, QThreadPool
from PySide2.QtGui import QTextCursor

from progonpy.domain.models import TestResult, TestReport, TestStatus
from progonpy.services.device_test import DeviceTestService
from progonpy.workers.tasks import TestTask


class TestPanel(QWidget):
    """Панель для запуска и отображения результатов тестирования"""
    
    def __init__(self, test_service: DeviceTestService, parent=None):
        super().__init__(parent)
        self.test_service = test_service
        self.current_address: int = 0
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        
        # Заголовок
        self.lbl_title = QLabel("🧪 Тестирование устройства")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.lbl_title)
        
        # Информация об устройстве
        self.lbl_device = QLabel("Адрес: —")
        layout.addWidget(self.lbl_device)
        
        # Прогресс
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        
        self.lbl_status = QLabel("Готов к тесту")
        layout.addWidget(self.lbl_status)
        
        # Кнопки управления
        btn_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("▶ Запустить тест")
        self.btn_start.clicked.connect(self.start_test)
        btn_layout.addWidget(self.btn_start)
        
        self.btn_cancel = QPushButton("⏹ Остановить")
        self.btn_cancel.clicked.connect(self.cancel_test)
        self.btn_cancel.setEnabled(False)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
        
        # Лог результатов
        group_log = QGroupBox("Результаты")
        log_layout = QVBoxLayout()
        
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFontFamily("Consolas")
        self.txt_log.setFontPointSize(9)
        log_layout.addWidget(self.txt_log)
        
        group_log.setLayout(log_layout)
        layout.addWidget(group_log)
        
        # Статистика
        self.lbl_stats = QLabel()
        layout.addWidget(self.lbl_stats)
        
        layout.addStretch()
    
    def _connect_signals(self) -> None:
        # Сигналы от TestTask будут подключаться при запуске
        pass
    def set_device(self, address: int) -> None:
        """Установить адрес устройства для теста"""
        self.current_address = address
        self.lbl_device.setText(f"Адрес: {address}")
        self.txt_log.clear()
        self.lbl_stats.clear()
        self.progress.setValue(0)
        self.lbl_status.setText("Готов к тесту")
    
    def _log(self, message: str, level: str = "info") -> None:
        """Добавить сообщение в лог"""
        colors = {"info": "#000", "success": "#0a0", "error": "#a00", "warning": "#aa0"}
        color = colors.get(level, "#000")
        self.txt_log.append(f'<span style="color:{color}">{message}</span>')
        self.txt_log.moveCursor(QTextCursor.End)
    
    @Slot()
    def start_test(self) -> None:
        if not self.current_address:
            self._log("⚠️  Сначала выберите устройство", "warning")
            return
        
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.txt_log.clear()
        self.progress.setValue(0)
        self.lbl_status.setText("Выполнение...")
        
        # Создаём и запускаем задачу
        self.task = TestTask(self.test_service, self.current_address)
        self.task.signals.progress.connect(self._on_progress)
        self.task.signals.step_result.connect(self._on_step_result)
        self.task.signals.finished.connect(self._on_finished)
        self.task.signals.error.connect(self._on_error)
        
        QThreadPool.globalInstance().start(self.task)
        self._log(f"🚀 Запуск теста для устройства #{self.current_address}")
    
    @Slot()
    def cancel_test(self) -> None:
        if hasattr(self, 'task'):
            self.task.cancel()
            self._log("⏹ Тест остановлен пользователем", "warning")
            self._reset_ui()
    
    @Slot(str, float)
    def _on_progress(self, message: str, percent: float) -> None:
        self.progress.setValue(int(percent))
        self.lbl_status.setText(message)
    
    @Slot(object)
    def _on_step_result(self, result: TestResult) -> None:
        status_icon = {
            TestStatus.SUCCESS: "✅",
            TestStatus.FAILED: "❌",
            TestStatus.SKIPPED: "⚪",
        }.get(result.status, "❓")
        
        msg = f"{status_icon} {result.step.name}: "
        if result.status == TestStatus.SUCCESS:
            msg += f"OK ({result.duration_ms:.1f} мс)"
            self._log(msg, "success")
        else:
            msg += f"FAIL — {result.error or 'Неизвестная ошибка'}"
            self._log(msg, "error")
    
    @Slot(object)
    def _on_finished(self, report: TestReport) -> None:
        success_count = sum(1 for s in report.steps if s.is_success)
        total = len(report.steps)
        
        self._log(f"\n🏁 Тест завершён за {report.duration_ms:.0f} мс")
        self._log(f"📊 Результат: {success_count}/{total} шагов успешно")
        
        if report.is_success:
            self.lbl_status.setText("✅ Тест пройден")
            self._log("🎉 Устройство работает корректно!", "success")
        else:
            self.lbl_status.setText("❌ Тест не пройден")
            self._log("⚠️  Обнаружены ошибки. Проверьте подключение и настройки.", "warning")
        
        # Статистика
        self.lbl_stats.setText(
            f"Всего шагов: {total} | Успешно: {success_count} | "
            f"Провалено: {total - success_count} | Время: {report.duration_ms:.0f} мс"
        )
        
        self._reset_ui()
    
    @Slot(str)
    def _on_error(self, error: str) -> None:
        self._log(f"💥 Ошибка: {error}", "error")
        self.lbl_status.setText("❌ Ошибка выполнения")
        self._reset_ui()
    
    def _reset_ui(self) -> None:
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)