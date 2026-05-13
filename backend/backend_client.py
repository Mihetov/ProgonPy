import subprocess
import requests
import time
import threading
import logging
from enum import Enum


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

    def open_rtu(self, port, baud=115200, stop_bits=1, parity="none"):
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

    def close_transport(self):
        resp = self._rpc("transport.close")

        if "error" not in resp:
            self.transport_active = False

        return resp

    def status(self):
        return self._rpc("transport.status")

    def serial_ports(self):
        return self._rpc("transport.serial_ports")

    def read(self, slave, address, count=1):
        if self.state != BackendState.READY:
            return {"error": "backend_not_ready"}

        if not self.transport_active:
            return {"error": "transport_not_active"}

        return self._rpc("modbus.read", {
            "slave_id": slave,
            "address": address,
            "count": count
        }, timeout=2.0, retry=1)

    def write(self, slave, address, values):
        if self.state != BackendState.READY:
            return {"error": "backend_not_ready"}

        return self._rpc("modbus.write", {
            "slave_id": slave,
            "address": address,
            "values": values
        })
