from __future__ import annotations
import time
from .base import BaseSensor, Measurement

try:
    import adafruit_dht  # type: ignore[import-untyped]
    import board  # type: ignore[import-untyped]
    _HW_AVAILABLE = True
except Exception:
    _HW_AVAILABLE = False


class DHT22Sensor(BaseSensor):
    """DHT11 or DHT22 temperature/humidity sensor via GPIO."""

    def _configure(self, config: dict) -> None:
        pin_num = config.get("pin", 4)
        sensor_type = config.get("sensor_type", 22)
        if _HW_AVAILABLE:
            gpio_pin = getattr(board, f"D{pin_num}")
            if sensor_type == 11:
                self._device = adafruit_dht.DHT11(gpio_pin, use_pulseio=False)
            else:
                self._device = adafruit_dht.DHT22(gpio_pin, use_pulseio=False)
        else:
            self._device = None

    def read(self) -> Measurement:
        if not _HW_AVAILABLE or self._device is None:
            raise RuntimeError("adafruit-circuitpython-dht not available")
        temperature = self._device.temperature
        humidity = self._device.humidity
        if temperature is None or humidity is None:
            raise RuntimeError("DHT sensor returned no data — retry next cycle")
        return Measurement(
            name=self.name,
            values={
                "temperature_c": round(float(temperature), 2),
                "humidity_pct": round(float(humidity), 2),
            },
            timestamp=time.time(),
        )
