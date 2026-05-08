# ProgonPy

Модульное UI-приложение для тестирования устройств по Modbus RTU.

## Ключевые возможности
- Слоистая архитектура: `domain -> services -> infra -> ui`.
- Параллельные проверки устройств (ThreadPoolExecutor).
- Сохранение и загрузка профиля подключения к COM-порту.
- Поиск устройств по ID с выбором типа после обнаружения.
- Переход от CLI к desktop UI (PySide6).
- Подготовка к сборке в `.exe` через PyInstaller.

## Быстрый старт
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
progonpy
```

## Сборка в EXE
```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name ProgonPy src/progonpy/app/main.py
```

## Структура
- `src/progonpy/domain` — сущности и контракты.
- `src/progonpy/services` — бизнес-логика (сканирование, тесты).
- `src/progonpy/infra` — serial/modbus и хранение настроек.
- `src/progonpy/ui` — UI-слой.
- `src/progonpy/workers` — фоновое выполнение задач.
