# ProgonPy

ProgonPy — desktop GUI-приложение на `tkinter` для работы с Modbus-устройствами через внешний backend-процесс (`Server.exe`) по JSON-RPC.

Проект ориентирован на модульный подход: UI-функциональность разбивается на отдельные виджеты, которые подхватываются автоматически.

---

## Содержание

- [Возможности](#возможности)
- [Стек и структура проекта](#стек-и-структура-проекта)
- [Как это работает (поток запуска)](#как-это-работает-поток-запуска)
- [Требования и окружение](#требования-и-окружение)
- [Быстрый старт](#быстрый-старт)
- [JSON-RPC контракт с backend](#json-rpc-контракт-с-backend)
- [Подробно о модульных виджетах](#подробно-о-модульных-виджетах)
  - [Контракт виджета](#контракт-виджета)
  - [Пошаговая инструкция по созданию модульного виджета](#пошаговая-инструкция-по-созданию-модульного-виджета)
  - [Шаблон виджета](#шаблон-виджета)
  - [Как работает автопоиск модулей](#как-работает-автопоиск-модулей)
  - [Отладка и типовые ошибки](#отладка-и-типовые-ошибки)
- [Live-опрос (Poller)](#live-опрос-poller)
- [Сборка в EXE (PyInstaller)](#сборка-в-exe-pyinstaller)
- [Динамическая замена виджетов после сборки](#динамическая-замена-виджетов-после-сборки)
- [Практические рекомендации](#практические-рекомендации)

---

## Возможности

- Автоматический запуск backend (`Server.exe`) при старте GUI.
- Работа по JSON-RPC (`requests`): ping, transport-методы, modbus read/write.
- Настройка RTU-подключения (COM-порт, baudrate, parity, stop bits).
- Live-опрос регистров с заданным интервалом.
- Модульная архитектура интерфейса: виджеты подключаются без правок ядра GUI.
- Поддержка внешней папки виджетов рядом с EXE (runtime-расширение в проде).

---

## Стек и структура проекта

- **Python 3.10+**
- **tkinter/ttk** — GUI
- **requests** — HTTP/JSON-RPC клиент
- **PyInstaller** — сборка standalone-дистрибутива

```text
ProgonPy/
├─ main.py                       # bootstrap: logger, порт, backend lifecycle, запуск окна
├─ Server.exe                    # внешний backend (обязателен для runtime)
├─ backend/
│  ├─ backend_client.py          # основной JSON-RPC клиент + state machine backend
│  └─ types.py                   # legacy/пример клиента (сейчас не используется ядром)
├─ gui/
│  ├─ app.py                     # главное окно, стили, навигация, загрузка виджетов
│  ├─ state/
│  │  └─ poller.py               # поток live-опроса Modbus
│  └─ widgets/
│     ├─ transport_widget.py     # настройка/подключение COM
│     ├─ modbus_widget_read.py   # live-чтение регистров
│     └─ log_widget.py           # простой лог-виджет (не в основном меню)
└─ build_tools/
   └─ build_exe.py               # скрипт сборки PyInstaller
```

---

## Как это работает (поток запуска)

1. `main.py` поднимает логгер и выбирает свободный localhost-порт.
2. Создаётся `BackendClient(exe_path="Server.exe", host="127.0.0.1", port=<free_port>)`.
3. `BackendClient.start_server(["--mode", "api", "--api-port", <port>])` запускает backend и ждёт успешный `ping`.
4. Создаётся `MainWindow(client=client, logger=log)`.
5. Внутри `MainWindow` создаётся общий `Poller`, строится UI, сканируются виджеты.
6. При закрытии окна останавливается poller и завершается backend-процесс.

---

## Требования и окружение

Минимально:

- Python 3.10+
- `Server.exe` в корне проекта
- Установленные зависимости:

```bash
pip install requests
```

> `tkinter` обычно поставляется с CPython. Если не установлен (редко на Linux), установите пакет вашей ОС (например `python3-tk`).

---

## Быстрый старт

```bash
python main.py
```

Рекомендуемый пользовательский сценарий после запуска:

1. Откройте модуль **«Настройка COM-порта»**.
2. Нажмите **Refresh**, выберите COM-порт.
3. Выставьте baud/parity/stop bits и нажмите **Connect**.
4. Перейдите в **Modbus Read**.
5. Укажите slave/address/count/interval и нажмите **Start Live**.

---

## JSON-RPC контракт с backend

Приложение ожидает, что backend поддерживает методы:

- `ping`
- `transport.open`
- `transport.close`
- `transport.status`
- `transport.serial_ports`
- `modbus.read`
- `modbus.write`

### Пример формата запроса

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "modbus.read",
  "params": {
    "slave_id": 1,
    "address": 0,
    "count": 10
  }
}
```

---

## Подробно о модульных виджетах

### Контракт виджета

Чтобы виджет появился в левом меню модулей, класс должен:

1. Быть объявлен в `.py`-файле внутри `gui/widgets/` (или во внешней `gui/widgets` рядом с EXE).
2. Иметь атрибут `IS_APP_WIDGET = True`.
3. Иметь атрибут `PANEL_TITLE = "Имя в меню"`.
4. Иметь конструктор совместимого вида:

```python
def __init__(self, parent, client, poller=None, on_log=None):
    ...
```

Где:

- `parent` — родительский контейнер tkinter/ttk;
- `client` — экземпляр `BackendClient` для RPC-вызовов;
- `poller` — общий экземпляр `Poller` (если виджету нужен live-режим);
- `on_log` — callback для логирования сообщений в общий лог приложения.

### Пошаговая инструкция по созданию модульного виджета

1. Создайте файл, например: `gui/widgets/device_status_widget.py`.
2. Создайте класс (обычно наследник `ttk.LabelFrame`).
3. Добавьте обязательные атрибуты `IS_APP_WIDGET` и `PANEL_TITLE`.
4. Реализуйте UI в `_build()`.
5. Для RPC используйте `self.client.<method>()`.
6. Для сервисных сообщений используйте `self.on_log("...")`.
7. Если нужен polling — используйте переданный `self.poller` (или отдельный собственный поток, но аккуратно с остановкой).
8. Перезапустите приложение: новый модуль появится автоматически.

### Шаблон виджета

```python
import tkinter as tk
from tkinter import ttk, messagebox


class DeviceStatusWidget(ttk.LabelFrame):
    IS_APP_WIDGET = True
    PANEL_TITLE = "Статус устройства"

    def __init__(self, parent, client, poller=None, on_log=None):
        super().__init__(parent, text=self.PANEL_TITLE, style="Card.TLabelframe")
        self.client = client
        self.poller = poller
        self.on_log = on_log

        self.slave = tk.StringVar(value="1")
        self.addr = tk.StringVar(value="0")
        self._build()

    def _build(self):
        body = ttk.Frame(self, style="Panel.TFrame")
        body.pack(fill="x")

        ttk.Label(body, text="Slave ID", style="App.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(body, textvariable=self.slave, style="App.TEntry").grid(row=1, column=0, sticky="ew")

        ttk.Label(body, text="Address", style="App.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Entry(body, textvariable=self.addr, style="App.TEntry").grid(row=1, column=1, sticky="ew")

        ttk.Button(body, text="Прочитать", command=self.read_once, style="App.TButton").grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )

        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

    def read_once(self):
        try:
            slave = int(self.slave.get())
            addr = int(self.addr.get())
        except ValueError:
            messagebox.showerror("Input Error", "Введите корректные числа")
            return

        resp = self.client.read(slave, addr, count=1)
        if "error" in resp:
            messagebox.showerror("Read Error", str(resp["error"]))
            if self.on_log:
                self.on_log(f"Read failed: {resp['error']}")
            return

        if self.on_log:
            self.on_log(f"Read OK: {resp}")
```

### Как работает автопоиск модулей

`MainWindow` сканирует **две** директории:

1. Внешнюю: `<папка_с_exe>/gui/widgets` (приоритетнее для runtime-override)
2. Внутреннюю: `gui/widgets` внутри проекта/сборки

Далее:

- импортирует модуль;
- ищет классы, объявленные **в самом модуле**;
- оставляет только классы с `IS_APP_WIDGET = True`;
- сортирует по `PANEL_TITLE`;
- создаёт кнопки в левом меню.

Если модуль не загрузился, ошибка пишется в лог через `append_log`.

### Отладка и типовые ошибки

- **Виджет не появился в меню**
  - проверьте `IS_APP_WIDGET = True`;
  - проверьте, что класс объявлен в модуле напрямую;
  - проверьте, что файл лежит в `gui/widgets`.

- **Ошибка при импорте виджета**
  - проверьте зависимости/опечатки;
  - проверьте, что код совместим с версией Python в runtime.

- **Падает конструктор виджета**
  - проверьте сигнатуру `__init__(parent, client, poller=None, on_log=None)`.

- **`read` возвращает `transport_not_active`**
  - сначала подключите transport в `TransportWidget` (кнопка Connect).

---

## Live-опрос (Poller)

`Poller` в `gui/state/poller.py`:

- работает в daemon-потоке;
- циклически вызывает `client.read(...)`;
- передаёт данные в callback `on_data`;
- поддерживает параметры: `slave`, `start_addr`, `count`, `interval`;
- корректно останавливается при закрытии окна.

Важно: в приложении используется **один общий poller**, передаваемый в виджеты. Если делаете собственный polling в модуле, обязательно реализуйте корректную остановку потоков.

---

## Сборка в EXE (PyInstaller)

### Установка

```bash
pip install pyinstaller
```

### Сборка

```bash
python build_tools/build_exe.py
```

Скрипт включает:

- `--collect-submodules gui.widgets`
- `--collect-submodules gui.state`
- `--collect-submodules backend`

Это важно для динамических импортов виджетов.

Результат: `dist/ProgonPy/`.

---

## Динамическая замена виджетов после сборки

Можно менять/добавлять виджеты **без пересборки EXE**:

1. Используйте папочную сборку (`dist/ProgonPy/`, не onefile).
2. Создавайте/изменяйте модули в `dist/ProgonPy/gui/widgets/`.
3. Соблюдайте контракт виджета (`IS_APP_WIDGET`, `PANEL_TITLE`, совместимый `__init__`).
4. Перезапускайте приложение.

За счёт приоритета внешней папки ваши runtime-виджеты будут подхвачены первыми.

---

## Практические рекомендации

- Для новых модулей придерживайтесь принципа: **1 виджет = 1 бизнес-сценарий**.
- Общий UI-стиль берите из существующих `ttk`-стилей (`App.TLabel`, `App.TButton`, `Card.TLabelframe`).
- Валидацию входных параметров делайте до RPC-вызовов.
- Ошибки пользователя показывайте через `messagebox`, сервисные события — через `on_log`.
- Если добавляете новый backend-метод, сначала оберните его в `BackendClient`, затем используйте в виджете.

---

Если нужно, могу дополнительно подготовить:

- отдельный `docs/widget_api.md` с формальным интерфейсом;
- шаблон генератора нового виджета (`python tools/new_widget.py <name>`);
- чеклист ревью модулей перед релизом.
