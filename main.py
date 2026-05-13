# app/main.py

import logging
import sys
import socket
from backend.backend_client import BackendClient
from gui.app import MainWindow


# =========================================================
# LOGGER
# =========================================================
def create_logger():
    logger = logging.getLogger("APP")
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        "%H:%M:%S"
    )

    handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(handler)

    return logger

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
# =========================================================
# BOOTSTRAP
# =========================================================
def main():
    log = create_logger()
    log.info("Starting application...")

    port = find_free_port()
    log.info(f"Selected free port: {port}")

    # -------------------------
    # BACKEND CLIENT
    # -------------------------
    client = BackendClient(
        exe_path="Server.exe",
        host="127.0.0.1",
        port=port,
        logger=log
    )

    # 🔥 ВАЖНО: СНАЧАЛА СТАРТ СЕРВЕРА
    client.start_server([
        "--mode", "api",
        "--api-port", str(port)
    ])

    # -------------------------
    # GUI (ТОЛЬКО ПОСЛЕ READY)
    # -------------------------
    app = MainWindow(client=client, logger=log)

    try:
        app.run()

    except KeyboardInterrupt:
        log.warning("Interrupted by user")

    finally:
        log.info("Stopping backend...")
        client.stop_server()

# =========================================================
if __name__ == "__main__":
    main()