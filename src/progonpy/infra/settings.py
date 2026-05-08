from __future__ import annotations

import json
from pathlib import Path

from progonpy.domain.models import SerialConfig


class SettingsRepository:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path.home() / ".progonpy.json"

    def load_serial_config(self) -> SerialConfig | None:
        if not self._path.exists():
            return None
        data = json.loads(self._path.read_text(encoding="utf-8"))
        return SerialConfig(**data["serial"])

    def save_serial_config(self, config: SerialConfig) -> None:
        payload = {"serial": config.__dict__}
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
