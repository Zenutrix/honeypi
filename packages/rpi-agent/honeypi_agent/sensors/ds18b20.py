from __future__ import annotations
import time
from .base import BaseSensor, Measurement

try:
    from w1thermsensor import W1ThermSensor  # type: ignore[import-untyped]
except Exception:
    W1ThermSensor = None  # type: ignore[assignment,misc]


class DS18B20Sensor(BaseSensor):
    def _configure(self, config: dict) -> None:
        if W1ThermSensor is None:
            raise RuntimeError("w1thermsensor package not installed")
        self._sensor = W1ThermSensor()

    def read(self) -> Measurement:
        temp = self._sensor.get_temperature()
        return Measurement(
            name=self.name,
            values={"temperature_c": temp},
            timestamp=time.time(),
        )
