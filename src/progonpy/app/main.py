from __future__ import annotations

import sys
import logging
from PySide2.QtWidgets import QApplication

from progonpy.app.service import ApplicationService
from progonpy.ui.main_window import MainWindow

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout), # Вывод в консоль
        # logging.FileHandler("progonpy.log", encoding="utf-8") # Раскомментируйте для записи в файл
    ]
)

logger = logging.getLogger(__name__)

def main() -> None:
    logger.info("Starting ProgonPy application...")
    app = QApplication(sys.argv)
    
    try:
        service = ApplicationService()
        window = MainWindow(service)
        window.show()
        logger.info("Main window created and shown.")
        sys.exit(app.exec_())
    except Exception as e:
        logger.critical("Application failed to start", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()