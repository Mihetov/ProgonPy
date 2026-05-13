# ProgonPy

Desktop GUI-приложение для работы с Modbus через внешний backend (`Server.exe`) по JSON-RPC.

## Что умеет

- Поднимает backend-процесс автоматически при старте приложения.
- Позволяет настраивать RTU-подключение (COM-порт, скорость, parity, stop bits).
- Поддерживает live-опрос Modbus регистров с настраиваемым интервалом.
- Использует модульный GUI: виджеты обнаруживаются автоматически из папки `gui/widgets`.

## Быстрый старт

### Требования

- Python 3.10+
- `Server.exe` в корне проекта
- Установленные Python зависимости:
  - `requests`
  - `tkinter` (обычно поставляется вместе с Python)

### Запуск

```bash
python main.py
```

## Архитектура

- `main.py` — bootstrap приложения, запуск/остановка backend, инициализация GUI.
- `backend/backend_client.py` — клиент JSON-RPC, управление lifecycle backend, transport/modbus вызовы.
- `gui/app.py` — главное окно, стилизация, левое меню модулей, загрузка/переключение виджетов.
- `gui/state/poller.py` — потоковый live-опрос Modbus.
- `gui/widgets/*` — отдельные UI-модули.

## Модульная система виджетов

Главное окно автоматически сканирует `gui/widgets` и добавляет найденные виджеты в левый список модулей.

Чтобы ваш виджет появился в приложении:

1. Создайте новый файл в `gui/widgets`, например `my_widget.py`.
2. Опишите класс виджета (обычно наследник `ttk.LabelFrame`).
3. Добавьте в класс:

```python
IS_APP_WIDGET = True
PANEL_TITLE = "Мой виджет"
```

4. Поддержите совместимый конструктор:

```python
def __init__(self, parent, client, poller=None, on_log=None):
    ...
```

- `client` — backend-клиент (`BackendClient`)
- `poller` — общий poller для live-опроса (если нужен)
- `on_log` — callback для вывода сервисных сообщений

Если `IS_APP_WIDGET` не задан или `False`, виджет в меню не появится.

## Примечания

- При закрытии окна poller останавливается корректно.
- Ошибки подключения/валидации отображаются через GUI-диалоги.
- Backend должен поддерживать методы:
  - `ping`
  - `transport.open`, `transport.close`, `transport.status`, `transport.serial_ports`
  - `modbus.read`, `modbus.write`


## Сборка в EXE (с сохранением модульных виджетов)

Используем `PyInstaller` и **обязательно** подключаем все подмодули `gui.widgets`,
чтобы динамическая загрузка через `pkgutil/importlib` продолжала работать в сборке.

### 1) Установка сборщика

```bash
pip install pyinstaller
```

### 2) Сборка

```bash
python build_tools/build_exe.py
```

### Что важно для модульности

- В build-команде используется:
  - `--collect-submodules gui.widgets`
  - `--collect-submodules gui.state`
- Это гарантирует, что все виджеты попадут в сборку, даже если они не импортируются напрямую в `main.py`.
- Механика `IS_APP_WIDGET` / `PANEL_TITLE` остается прежней: добавили модуль в `gui/widgets` → он будет доступен после пересборки EXE.

### Результат

После сборки исполняемый файл и окружение будут в:

- `dist/ProgonPy/`
