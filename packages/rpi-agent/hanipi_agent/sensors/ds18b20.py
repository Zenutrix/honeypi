from __future__ import annotations

import glob
import time
from pathlib import Path
from typing import Any

from .base import BaseSensor, Measurement

_W1_BASE = Path("/sys/bus/w1/devices")


def _find_devices() -> list[Path]:
    return sorted(Path(p) for p in glob.glob(str(_W1_BASE / "28-*" / "w1_slave")))


def _read_temp(device: Path) -> float:
    lines = device.read_text().splitlines()
    if not lines or "YES" not in lines[0]:
        raise RuntimeError(f"CRC-Fehler beim Lesen von {device}")
    temp_part = lines[1].split("t=")
    if len(temp_part) < 2:
        raise RuntimeError(f"Ungültiges Datenformat: {device}")
    return round(int(temp_part[1]) / 1000.0, 2)


class DS18B20Sensor(BaseSensor):
    """DS18B20 1-Wire Temperatursensor (liest direkt aus /sys/bus/w1/devices)."""

    def _configure(self, config: dict[str, Any]) -> None:
        self._index = int(config.get("sensor_index", 0))
        self._sensor_id: str | None = config.get("sensor_id")

    def _get_device(self) -> Path:
        if self._sensor_id:
            device = _W1_BASE / self._sensor_id / "w1_slave"
            if not device.exists():
                raise RuntimeError(f"DS18B20 mit ID '{self._sensor_id}' nicht gefunden")
            return device
        devices = _find_devices()
        if not devices:
            raise RuntimeError(
                "Kein DS18B20 am 1-Wire Bus (dtoverlay=w1-gpio in config.txt?)"
            )
        if self._index >= len(devices):
            raise RuntimeError(
                f"DS18B20 Index {self._index} nicht vorhanden "
                f"({len(devices)} Sensor(en) angeschlossen)"
            )
        return devices[self._index]

    def read(self) -> Measurement:
        temp = _read_temp(self._get_device())
        return Measurement(
            name=self.name,
            values={"temperature_c": temp},
            timestamp=time.time(),
            hive_id=self.hive_id,
        )
