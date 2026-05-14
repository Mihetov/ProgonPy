import subprocess
import requests
import time
import threading
import logging
from enum import Enum
from typing import Optional, Union, List, Dict, Any


class BackendState(Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    READY = "READY"
    ERROR = "ERROR"


class BackendClient:
    def __init__(self, exe_path, host="127.0.0.1", port=8001, logger=None):
        self.exe_path = exe_path
        self.host = host
        self.port = port

        self.url = self._build_url()

        self.process = None
        self.state = BackendState.STOPPED

        self.transport_active = False

        self.log = logger or logging.getLogger("BackendClient")
        self._lock = threading.Lock()

    def _build_url(self):
        return f"http://{self.host}:{self.port}"

    def set_port(self, port: int):
        with self._lock:
            self.port = port
            self.url = self._build_url()

    def _rpc(self, method, params=None, timeout=2.0, retry=1):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }

        last_error = None

        for attempt in range(retry + 1):
            try:
                self.log.debug(f"[RPC →] {method} {params}")

                r = requests.post(
                    self.url,
                    json=payload,
                    timeout=timeout
                )
                r.raise_for_status()
                data = r.json()

                self.log.debug(f"[RPC ←] {data}")
                return data

            except Exception as e:
                last_error = e
                self.log.error(f"[RPC FAIL] {method} attempt {attempt}: {e}")
                time.sleep(0.2)

        return {"error": str(last_error)}

    # ==================== Управление сервером ====================
    
    def start_server(self, args=None):
        args = args or []

        with self._lock:
            if self.state != BackendState.STOPPED:
                return

            self.state = BackendState.STARTING
            self.log.info("Starting backend...")

            self.process = subprocess.Popen(
                [self.exe_path] + args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        for _ in range(80):
            resp = self._rpc("ping", timeout=1.0)

            if resp.get("result", {}).get("status") == "ok":
                with self._lock:
                    self.state = BackendState.READY
                self.log.info("Backend READY")
                return

            time.sleep(0.25)

        with self._lock:
            self.state = BackendState.ERROR

        raise RuntimeError("Backend not responding")

    def stop_server(self):
        with self._lock:
            self.log.info("Stopping backend...")

            if self.process:
                self.process.terminate()
                self.process.kill()
                self.process = None

            self.state = BackendState.STOPPED
            self.transport_active = False

    def is_ready(self):
        return self.state == BackendState.READY

    def ping(self) -> Dict[str, Any]:
        """Проверка доступности сервера"""
        return self._rpc("ping")

    # ==================== Транспорт: общая информация ====================
    
    def serial_ports(self) -> Dict[str, Any]:
        """Получить список доступных последовательных портов"""
        return self._rpc("transport.serial_ports")

    def transport_status(self) -> Dict[str, Any]:
        """Получить статус активного транспорта"""
        return self._rpc("transport.status")

    def close_transport(self) -> Dict[str, Any]:
        """Закрыть активное транспортное соединение"""
        resp = self._rpc("transport.close")
        if "error" not in resp:
            self.transport_active = False
        return resp

    # ==================== Транспорт: открытие ====================
    
    def open_rtu(self, port: str, baud: int = 115200, 
                 stop_bits: int = 1, parity: str = "none") -> Dict[str, Any]:
        """Открыть RTU-соединение"""
        resp = self._rpc("transport.open", {
            "type": "rtu",
            "serial_port": port,
            "baud_rate": baud,
            "stop_bits": stop_bits,
            "parity": parity,
        })
        if "error" not in resp:
            self.transport_active = True
        return resp

    def open_tcp(self, host: str, port: int) -> Dict[str, Any]:
        """Открыть TCP-соединение"""
        resp = self._rpc("transport.open", {
            "type": "tcp",
            "host": host,
            "port": port,
        })
        if "error" not in resp:
            self.transport_active = True
        return resp

    def switch_transport_rtu(self, port: str, baud: int = 115200,
                             stop_bits: int = 1) -> Dict[str, Any]:
        """Переключить транспорт на RTU (закрывает предыдущий)"""
        resp = self._rpc("transport.switch", {
            "type": "rtu",
            "serial_port": port,
            "baud_rate": baud,
            "stop_bits": stop_bits,
        })
        if "error" not in resp:
            self.transport_active = True
        return resp

    def switch_transport_tcp(self, host: str, port: int) -> Dict[str, Any]:
        """Переключить транспорт на TCP (закрывает предыдущий)"""
        resp = self._rpc("transport.switch", {
            "type": "tcp",
            "host": host,
            "port": port,
        })
        if "error" not in resp:
            self.transport_active = True
        return resp

    # ==================== Modbus: чтение ====================
    
    def read(self, slave: int, address: Union[int, str], 
             count: int = 1, input: bool = False, 
             timeout_ms: int = 2000) -> Dict[str, Any]:
        """
        Читать регистры Modbus.
        
        :param slave: ID устройства (0-255)
        :param address: Адрес регистра (int или hex-строка, например "0xF000")
        :param count: Количество регистров
        :param input: True для Input Registers, False для Holding Registers
        :param timeout_ms: Таймаут в миллисекундах
        """
        if self.state != BackendState.READY:
            return {"error": "backend_not_ready"}
        if not self.transport_active:
            return {"error": "transport_not_active"}

        return self._rpc("modbus.read", {
            "slave_id": slave,
            "address": address,  # Сервер принимает int или hex-строку
            "count": count,
            "input": input,
            "timeout_ms": timeout_ms
        }, timeout=timeout_ms/1000 + 1.0, retry=1)

    def read_group(self, requests: List[Dict[str, Any]], 
                   timeout_ms: int = 2000) -> Dict[str, Any]:
        """
        Групповое чтение регистров (несколько запросов в одном вызове).
        
        :param requests: Список запросов, каждый с полями:
            - slave_id: int (0-255)
            - address: int или hex-строка
            - count: int
            - input: bool (опционально, по умолчанию False)
        :param timeout_ms: Общий таймаут для всей группы
        """
        if self.state != BackendState.READY:
            return {"error": "backend_not_ready"}
        if not self.transport_active:
            return {"error": "transport_not_active"}

        return self._rpc("modbus.read_group", {
            "requests": requests,
            "timeout_ms": timeout_ms
        }, timeout=timeout_ms/1000 + 1.0, retry=1)

    # ==================== Modbus: запись ====================
    
    def write(self, slave: int, address: Union[int, str], 
              values: Optional[Union[int, List[int]]] = None,
              value: Optional[int] = None) -> Dict[str, Any]:
        """
        Записать регистры Modbus.
        
        :param slave: ID устройства (0-255)
        :param address: Адрес регистра (int или hex-строка)
        :param values: Список значений для записи нескольких регистров
        :param value: Единственное значение для записи одного регистра
        """
        if self.state != BackendState.READY:
            return {"error": "backend_not_ready"}
        if not self.transport_active:
            return {"error": "transport_not_active"}

        params = {
            "slave_id": slave,
            "address": address,
        }
        
        if values is not None:
            if isinstance(values, int):
                values = [values]
            params["values"] = values
        elif value is not None:
            params["value"] = value
        else:
            return {"error": "value or values required"}

        return self._rpc("modbus.write", params)

    def write_group(self, requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Групповая запись регистров.
        
        :param requests: Список запросов, каждый с полями:
            - slave_id: int (0-255)
            - address: int или hex-строка
            - value: int (для одиночной записи) ИЛИ
            - values: List[int] (для множественной записи)
        """
        if self.state != BackendState.READY:
            return {"error": "backend_not_ready"}
        if not self.transport_active:
            return {"error": "transport_not_active"}

        return self._rpc("modbus.write_group", {
            "requests": requests
        })

    # ==================== Утилиты ====================
    
    def wait_ready(self, timeout: float = 20.0, poll_interval: float = 0.25) -> bool:
        """Ожидать перехода в состояние READY"""
        start = time.time()
        while time.time() - start < timeout:
            if self.is_ready():
                return True
            time.sleep(poll_interval)
        return False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_server()
        return False