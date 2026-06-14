from __future__ import annotations
import time
from .base import BaseSensor, Measurement

try:
    from w1thermsensor import W1ThermSensor  # type: ignore[import-untyped]
except Exception:
    W1ThermSensor = None  # type: ignore[assignment,misc]


class DS18B20Sensor(BaseSensor):
    """DS18B20 1-Wire temperature sensor.

    Multiple DS18B20 on the same bus: use sensor_index (0 = first, 1 = second …)
    or sensor_id (e.g. '28-0000000abc12') for stable identification.
    """

    def _configure(self, config: dict) -> None:
        if W1ThermSensor is None:
            raise RuntimeError("w1thermsensor package not installed")
        self._index = int(config.get("sensor_index", 0))
        self._sensor_id: str | None = config.get("sensor_id")

    def read(self) -> Measurement:
        if self._sensor_id:
            sensor = W1ThermSensor(sensor_id=self._sensor_id)
        else:
            available = W1ThermSensor.get_available_sensors()
            if not available:
                raise RuntimeError("Kein DS18B20 Sensor am 1-Wire Bus gefunden")
            if self._index >= len(available):
                raise RuntimeError(
                    f"DS18B20 Index {self._index} nicht vorhanden "
                    f"({len(available)} Sensor(en) angeschlossen)"
                )
            sensor = available[self._index]
        return Measurement(
            name=self.name,
            values={"temperature_c": round(sensor.get_temperature(), 2)},
            timestamp=time.time(),
        )
