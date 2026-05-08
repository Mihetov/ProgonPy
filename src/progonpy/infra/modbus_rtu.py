from __future__ import annotations

import time
import struct
import serial
import logging
from progonpy.domain.models import SerialConfig
import threading
logger = logging.getLogger(__name__)


class ModbusRtuClient:
    # Минимальная пауза между кадрами: 3.5 символа (в секундах)
    # Рассчитывается как: 3.5 * (10 бит / baudrate)
    INTER_FRAME_CHARS = 3.5
    BITS_PER_CHAR = 10  # 1 start + 8 data + 1 parity (или 0) + 1 stop (минимум)

    def __init__(self) -> None:
        
        self._send_lock = threading.Lock()
        self.serial: serial.Serial | None = None
        self._inter_frame_delay: float = 0.0035  # дефолт для 9600 бод

    def connect(self, config: SerialConfig) -> bool:
        stopbits_map = {
            1: serial.STOPBITS_ONE,
            1.5: serial.STOPBITS_ONE_POINT_FIVE,
            2: serial.STOPBITS_TWO,
        }
        try:
            logger.debug(
                f"Connecting to {config.port} with baudrate={config.baudrate}, "
                f"parity={config.parity}, stopbits={config.stopbits}"
            )
            self.serial = serial.Serial(
                port=config.port,
                baudrate=config.baudrate,
                parity=config.parity,
                stopbits=stopbits_map.get(config.stopbits, serial.STOPBITS_ONE),
                bytesize=config.bytesize,
                timeout=config.timeout,
                write_timeout=config.timeout,
            )
            # Пересчитываем межфреймовую задержку под текущий baudrate
            self._inter_frame_delay = (
                self.INTER_FRAME_CHARS * self.BITS_PER_CHAR / config.baudrate
            )
            logger.info(
                f"Connected to {config.port} (inter-frame delay: {self._inter_frame_delay*1000:.2f} ms)"
            )
            # Даем линии "успокоиться" после открытия
            time.sleep(0.1)
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect to {config.port}: {e}")
            return False

    def disconnect(self) -> None:
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.debug("Serial port closed.")

    @staticmethod
    def _crc(data: list[int]) -> int:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
        return crc

    def _wait_for_bus_idle(self) -> None:
        """Ждём, пока буфер приёма опустеет (защита от "мусора" на линии)"""
        if self.serial:
            self.serial.reset_input_buffer()

    def _request(self, frame: list[int]) -> list[int] | None:
        with self._send_lock:
            if not self.serial or not self.serial.is_open:
                logger.warning("Attempted to send request while serial port is closed.")
                return None

            # 1. Межфреймовая пауза ПЕРЕД отправкой (требование Modbus RTU)
            time.sleep(self._inter_frame_delay)
            
            # 2. Очищаем буфер от возможного мусора
            self._wait_for_bus_idle()

            crc = self._crc(frame)
            packet = bytes(frame + [crc & 0xFF, (crc >> 8) & 0xFF])

            try:
                logger.debug(f"Sending raw: {packet.hex()}")
                self.serial.write(packet)
                self.serial.flush()
                
                # 3. Критически важно: задержка для переключения RS-485 из TX в RX
                #    Без этого адаптер не успеет перейти в режим приёма и пропустит ответ
                time.sleep(0.005)  # 5 мс обычно достаточно, можно увеличить до 10-20 мс для медленных адаптеров

                # 4. Читаем ответ: сначала 1 байт, чтобы "разбудить" таймаут, потом остальное
                #    Используем небольшой таймаут на первый байт
                start_time = time.time()
                raw = b""
                
                # Ждём первый байт ответа (если устройство вообще ответит)
                while time.time() - start_time < self.serial.timeout:
                    byte = self.serial.read(1)
                    if byte:
                        raw += byte
                        break
                
                # Если первый байт получен — читаем остальное (указываем ожидаемую длину, если возможно)
                if raw:
                    # Минимальный ответ: addr(1) + func(1) + byte_count(1) + data(2+) + crc(2) = 5 байт
                    # Но лучше читать всё, что придёт за разумное время
                    remaining_timeout = max(0.05, self.serial.timeout - (time.time() - start_time))
                    self.serial.timeout = remaining_timeout
                    raw += self.serial.read(256)  # Читаем "на всякий случай", потом обрежем
                
                logger.debug(f"Received raw ({len(raw)} bytes): {raw.hex() if raw else 'EMPTY'}")

                if len(raw) < 5:
                    logger.debug(f"No valid response received (too short). Raw: {raw.hex() if raw else 'empty'}")
                    return None

                # 5. Проверка CRC ответа
                received_crc = raw[-1] << 8 | raw[-2]
                calculated_crc = self._crc(list(raw[:-2]))
                if received_crc != calculated_crc:
                    logger.warning(
                        f"CRC mismatch: received 0x{received_crc:04X}, calculated 0x{calculated_crc:04X}. "
                        f"Frame: {raw.hex()}"
                    )
                    return None

                # 6. Проверка на ошибку (функция с установленным битом 7)
                if raw[1] & 0x80:
                    exc_code = raw[2] if len(raw) > 2 else 0
                    logger.warning(f"Modbus exception from addr {raw[0]}: code 0x{exc_code:02X}")
                    return None

                return list(raw)

            except Exception as e:
                logger.error(f"Error during Modbus request: {type(e).__name__}: {e}")
                return None

    def read_registers(self, address: int, register: int, count: int) -> list[int] | None:
        resp = self._request([address, 0x03, register >> 8, register & 0xFF, count >> 8, count & 0xFF])
        if not resp or resp[1] != 0x03:
            # Если это не исключение (бит 7), то просто нет ответа
            if resp and resp[1] & 0x80:
                logger.warning(f"Read registers error: addr={address}, reg={register}, exc_code={resp[2] if len(resp)>2 else '?'}")
            else:
                logger.debug(f"Read registers failed (no valid response): addr={address}, reg={register}")
            return None

        byte_count = resp[2]
        expected_len = 3 + byte_count + 2  # header + data + crc
        if len(resp) < expected_len:
            logger.warning(f"Response too short: expected {expected_len}, got {len(resp)}")
            return None

        values = []
        for i in range(count):
            offset = 3 + i * 2
            if offset + 1 < len(resp):
                values.append((resp[offset] << 8) | resp[offset + 1])
        return values

    def write_register(self, address: int, register: int, value: int) -> bool:
        resp = self._request([address, 0x06, register >> 8, register & 0xFF, value >> 8, value & 0xFF])
        success = bool(resp and resp[1] == 0x06 and len(resp) >= 8)
        if not success:
            if resp and resp[1] & 0x80:
                logger.warning(f"Write register error: addr={address}, reg={register}, exc_code={resp[2] if len(resp)>2 else '?'}")
            else:
                logger.debug(f"Write register failed: addr={address}, reg={register}, val={value}")
        return success

    def write_registers(self, address: int, register: int, values: list[int]) -> bool:
        quantity = len(values)
        frame = [address, 0x10, register >> 8, register & 0xFF, quantity >> 8, quantity & 0xFF, quantity * 2]
        for value in values:
            frame.extend([value >> 8, value & 0xFF])
        
        resp = self._request(frame)
        success = bool(resp and resp[1] == 0x10 and len(resp) >= 8)
        if not success:
            if resp and resp[1] & 0x80:
                logger.warning(f"Write registers error: addr={address}, reg={register}, exc_code={resp[2] if len(resp)>2 else '?'}")
            else:
                logger.debug(f"Write registers failed: addr={address}, reg={register}")
        return success


def float_to_registers(value: float) -> tuple[int, int]:
    packed = struct.pack(">f", value)
    return ((packed[0] << 8) | packed[1], (packed[2] << 8) | packed[3])