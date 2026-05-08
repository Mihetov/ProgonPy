from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from progonpy.app.service import ApplicationService
from progonpy.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow(ApplicationService())
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
