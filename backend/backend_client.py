import subprocess
import requests
import time
import threading
import logging
import queue
import uuid

from enum import Enum
from typing import Optional, Union, List, Dict, Any


class BackendState(Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    READY = "READY"
    ERROR = "ERROR"

class RpcTask:
    def __init__(
        self,
        method: str,
        params: Optional[dict] = None,
        timeout: float = 0.2
    ):
        self.id = str(uuid.uuid4())
        self.method = method
        self.params = params or {}
        self.timeout = timeout
        self.done = threading.Event()
        self.response = None
        self.error = None

class BackendClient:

    def __init__(
        self,
        exe_path,
        host="127.0.0.1",
        port=8001,
        logger=None
    ):

        self.exe_path = exe_path
        self.host = host
        self.port = port
        self.url = self._build_url()
        self.process = None
        self.state = BackendState.STOPPED
        self.transport_active = False
        self.log = logger or logging.getLogger("BackendClient")
        self._lock = threading.Lock()
        self.rpc_queue = queue.Queue()
        self.worker_running = True
        self.worker = threading.Thread(
            target=self._rpc_worker,
            daemon=True
        )

        self.worker.start()

    def _build_url(self):
        return f"http://{self.host}:{self.port}"

    def set_port(self, port: int):

        with self._lock:
            self.port = port
            self.url = self._build_url()

    def _rpc_worker(self):
        session = requests.Session()
        while self.worker_running:
            try:
                task = self.rpc_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "id": task.id,
                    "method": task.method,
                    "params": task.params
                }
                self.log.debug(
                    f"[RPC →] {task.method} {task.params}"
                )
                response = session.post(
                    self.url,
                    json=payload,
                    timeout=(
                        min(task.timeout, 0.2),
                        task.timeout
                    )
                )

                response.raise_for_status()
                task.response = response.json()
                self.log.debug(
                    f"[RPC ←] {task.response}"
                )

            except Exception as e:
                task.error = str(e)
                self.log.error(
                    f"[RPC FAIL] {task.method}: {e}"
                )

            finally:

                task.done.set()

    def _rpc(
        self,
        method,
        params=None,
        timeout=0.2
    ):

        task = RpcTask(
            method=method,
            params=params,
            timeout=timeout
        )

        self.rpc_queue.put(task)

        finished = task.done.wait(timeout)

        if not finished:
            return {
                "error": "timeout"
            }
        if task.error:
            return {
                "error": task.error
            }
        return task.response

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
            resp = self._rpc(
                "ping",
                timeout=0.5
            )

            if resp.get("result", {}).get("status") == "ok":
                with self._lock:
                    self.state = BackendState.READY
                self.log.info("Backend READY")
                return
            time.sleep(0.25)

        with self._lock:
            self.state = BackendState.ERROR

        raise RuntimeError(
            "Backend not responding"
        )

    def stop_server(self):

        with self._lock:
            self.log.info("Stopping backend...")
            self.worker_running = False
            if self.process:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except:
                    self.process.kill()
                self.process = None

            self.state = BackendState.STOPPED
            self.transport_active = False

    def is_ready(self):
        return self.state == BackendState.READY

    def ping(self):
        return self._rpc(
            "ping",
            timeout=0.3
        )

    def serial_ports(self):

        return self._rpc(
            "transport.serial_ports",
            timeout=0.5
        )

    def transport_status(self):

        return self._rpc(
            "transport.status",
            timeout=0.3
        )

    def close_transport(self):

        resp = self._rpc(
            "transport.close",
            timeout=0.5
        )

        if "error" not in resp:
            self.transport_active = False

        return resp

    def open_rtu(
        self,
        port: str,
        baud: int = 115200,
        stop_bits: int = 1,
        parity: str = "none"
    ):

        resp = self._rpc(
            "transport.open",
            {
                "type": "rtu",
                "serial_port": port,
                "baud_rate": baud,
                "stop_bits": stop_bits,
                "parity": parity,
            },
            timeout=1.0
        )

        if "error" not in resp:
            self.transport_active = True

        return resp

    def open_tcp(
        self,
        host: str,
        port: int
    ):

        resp = self._rpc(
            "transport.open",
            {
                "type": "tcp",
                "host": host,
                "port": port,
            },
            timeout=1.0
        )

        if "error" not in resp:
            self.transport_active = True

        return resp

    def switch_transport_rtu(
        self,
        port: str,
        baud: int = 115200,
        stop_bits: int = 1
    ):

        resp = self._rpc(
            "transport.switch",
            {
                "type": "rtu",
                "serial_port": port,
                "baud_rate": baud,
                "stop_bits": stop_bits,
            },
            timeout=1.0
        )

        if "error" not in resp:
            self.transport_active = True

        return resp

    def switch_transport_tcp(
        self,
        host: str,
        port: int
    ):

        resp = self._rpc(
            "transport.switch",
            {
                "type": "tcp",
                "host": host,
                "port": port,
            },
            timeout=1.0
        )

        if "error" not in resp:
            self.transport_active = True

        return resp

    def read(
        self,
        slave: int,
        address: Union[int, str],
        count: int = 1,
        input: bool = False,
        timeout_ms: int = 200
    ) -> Dict[str, Any]:

        if self.state != BackendState.READY:
            return {
                "error": "backend_not_ready"
            }

        if not self.transport_active:
            return {
                "error": "transport_not_active"
            }

        timeout_sec = max(
            0.05,
            timeout_ms / 1000
        )

        return self._rpc(
            "modbus.read",
            {
                "slave_id": slave,
                "address": address,
                "count": count,
                "input": input,
                "timeout_ms": timeout_ms
            },
            timeout=timeout_sec
        )

    def read_group(
        self,
        requests_list: List[Dict[str, Any]],
        timeout_ms: int = 200
    ):

        if self.state != BackendState.READY:
            return {
                "error": "backend_not_ready"
            }

        if not self.transport_active:
            return {
                "error": "transport_not_active"
            }

        timeout_sec = max(
            0.05,
            timeout_ms / 1000
        )

        return self._rpc(
            "modbus.read_group",
            {
                "requests": requests_list,
                "timeout_ms": timeout_ms
            },
            timeout=timeout_sec
        )

    def write(
        self,
        slave: int,
        address: Union[int, str],
        values: Optional[
            Union[int, List[int]]
        ] = None,
        value: Optional[int] = None
    ):

        if self.state != BackendState.READY:
            return {
                "error": "backend_not_ready"
            }

        if not self.transport_active:
            return {
                "error": "transport_not_active"
            }

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
            return {
                "error": "value or values required"
            }

        return self._rpc(
            "modbus.write",
            params,
            timeout=0.5
        )

    def write_group(
        self,
        requests_list: List[Dict[str, Any]]
    ):

        if self.state != BackendState.READY:
            return {
                "error": "backend_not_ready"
            }

        if not self.transport_active:
            return {
                "error": "transport_not_active"
            }

        return self._rpc(
            "modbus.write_group",
            {
                "requests": requests_list
            },
            timeout=1.0
        )

    def wait_ready(
        self,
        timeout: float = 20.0,
        poll_interval: float = 0.25
    ) -> bool:

        start = time.time()

        while time.time() - start < timeout:

            if self.is_ready():
                return True

            time.sleep(poll_interval)

        return False

    def __enter__(self):

        return self

    def __exit__(
        self,
        exc_type,
        exc_val,
        exc_tb
    ):

        self.stop_server()

        return False