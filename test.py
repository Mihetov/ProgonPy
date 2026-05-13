import subprocess
import requests
import time
import logging


class ModbusBackendClient:
    def __init__(self, exe_path, host="127.0.0.1", port=8001):
        self.exe_path = exe_path
        self.url = f"http://{host}:{port}"
        self.process = None

        # state
        self.server_ready = True
        self.transport_active = False

        # -------------------------
        # LOGGER SETUP
        # -------------------------
        self.log = logging.getLogger("ModbusClient")
        self.log.setLevel(logging.DEBUG)

        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            "%H:%M:%S"
        )
        handler.setFormatter(formatter)

        if not self.log.handlers:
            self.log.addHandler(handler)

    # -------------------------
    # START SERVER
    # -------------------------
    def start(self, args=None):
        if args is None:
            args = []

        self.log.info("Starting server...")

        self.process = subprocess.Popen(
            [self.exe_path] + args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        for i in range(40):
            self.log.debug("send ping")

            try:
                resp = self.ping()

                self.log.debug(f"Ping raw response: {resp}")

                # 1. проверяем что это dict
                if not isinstance(resp, dict):
                    raise ValueError("Invalid response type")

                # 2. проверяем jsonrpc
                if resp.get("jsonrpc") != "2.0":
                    raise ValueError("Invalid jsonrpc response")

                # 3. проверяем result
                result = resp.get("result")
                if not isinstance(result, dict):
                    raise ValueError("No result field")

                # 4. финальный check
                if result.get("status") == "ok":
                    self.server_ready = True
                    self.log.info("Server is READY")
                    return

            except requests.exceptions.Timeout:
                self.log.debug(f"Timeout waiting server... ({i})")

            except requests.exceptions.ConnectionError:
                self.log.debug(f"Connection refused... ({i})")

            except Exception as e:
                self.log.debug(f"Waiting server... ({i}) {e}")

            time.sleep(0.5)

        self.log.error("Server failed to start")
        raise RuntimeError("Server did not start")
    # -------------------------
    # STOP SERVER
    # -------------------------
    def stop(self):
        self.log.info("Stopping server...")

        if self.process:
            self.process.terminate()
            self.process = None

        self.server_ready = False
        self.transport_active = False

    # -------------------------
    # RAW CALL
    # -------------------------
    def call(self, method, params=None):
        if not self.server_ready:
            raise RuntimeError("Server not ready")

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }

        self.log.debug(f"RPC → {method} | {params}")

        try:
            r = requests.post(self.url, json=payload, timeout=2.0)
            r.raise_for_status()
            data = r.json()

        except Exception as e:
            self.log.error(f"RPC error: {method} -> {e}")
            raise

        self.log.debug(f"RPC ← {data}")

        # track transport state
        if method == "transport.open" and "error" not in data:
            self.transport_active = True
            self.log.info("Transport OPENED")

        if method == "transport.close":
            self.transport_active = False
            self.log.info("Transport CLOSED")

        return data

    # -------------------------
    # BASIC API
    # -------------------------
    def ping(self):
        return self.call("ping")

    def status(self):
        return self.call("transport.status")

    def serial_ports(self):
        return self.call("transport.serial_ports")

    # -------------------------
    # RTU
    # -------------------------
    def open_rtu(self, port, baud=38400, stop_bits=1):
        self.log.info(f"Opening RTU: {port} @ {baud}")

        resp = self.call("transport.open", {
            "type": "rtu",
            "serial_port": port,
            "baud_rate": baud,
            "stop_bits": stop_bits
        })

        if "error" in resp:
            self.log.error(f"RTU open failed: {resp}")
            raise RuntimeError(resp)

        return resp

    def close_transport(self):
        self.log.info("Closing transport")
        return self.call("transport.close")

    # -------------------------
    # MODBUS
    # -------------------------
    def read(self, slave, address, count=1):
        self.log.info(f"READ slave={slave} addr={address} count={count}")

        if not self.transport_active:
            self.log.error("Read blocked: transport inactive")
            raise RuntimeError("Transport not active")

        resp = self.call("modbus.read", {
            "slave_id": slave,
            "address": address,
            "count": count
        })

        self.log.debug(f"READ result: {resp}")
        return resp

    def write(self, slave, address, values):
        self.log.info(f"WRITE slave={slave} addr={address} values={values}")

        if not self.transport_active:
            self.log.error("Write blocked: transport inactive")
            raise RuntimeError("Transport not active")

        resp = self.call("modbus.write", {
            "slave_id": slave,
            "address": address,
            "values": values
        })

        self.log.debug(f"WRITE result: {resp}")
        return resp

    # -------------------------
    # STATUS HELPERS
    # -------------------------
    def is_ready(self):
        return self.server_ready

    def is_transport_active(self):
        return self.transport_active


# =========================================================
# EXAMPLE
# =========================================================
if __name__ == "__main__":
    client = ModbusBackendClient(
        exe_path="Server.exe",
        host="127.0.0.1",
        port=8080
    )

    print(client.ping())

    print(client.serial_ports())

    client.open_rtu("COM19", 115200, 1)

    print(client.status())

    print(client.read(254, 0, 10))

    client.stop()