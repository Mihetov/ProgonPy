import threading
import time


class Poller:
    def __init__(self, client, on_data=None):
        self.client = client
        self.on_data = on_data

        self.running = False
        self.thread = None

        self.slave = 1
        self.start_addr = 0
        self.count = 10
        self.interval = 0.5

    def configure(self, slave, start_addr, count, interval=0.5):
        self.slave = slave
        self.start_addr = start_addr
        self.count = count
        self.interval = interval

    def start(self):
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.thread = None

    def _loop(self):
        next_time = time.time()

        while self.running:
            try:
                resp = self.client.read(
                    self.slave,
                    self.start_addr,
                    self.count
                )

                data = resp.get("result", {})
                if "error" in resp:
                    data = {"error": resp.get("error")}

                if self.on_data:
                    self.on_data(data)

            except Exception as e:
                if self.on_data:
                    self.on_data({"error": str(e)})

            next_time += self.interval
            sleep_time = next_time - time.time()

            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                next_time = time.time()
