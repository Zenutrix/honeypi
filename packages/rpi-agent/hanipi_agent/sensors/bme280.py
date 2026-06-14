from __future__ import annotations
import time
from .base import BaseSensor, Measurement

try:
    import smbus2  # type: ignore[import-untyped]
    import bme280 as bme280_module  # type: ignore[import-untyped]
except ImportError:
    smbus2 = None  # type: ignore[assignment]
    bme280_module = None  # type: ignore[assignment]


class BME280Sensor(BaseSensor):
    def _configure(self, config: dict) -> None:
        if smbus2 is None or bme280_module is None:
            raise RuntimeError("smbus2 or RPi.bme280 package not installed")
        port = config.get("i2c_port", 1)
        self._address = config.get("i2c_address", 0x76)
        self._bus = smbus2.SMBus(port)
        self._calibration = bme280_module.load_calibration_params(self._bus, self._address)

    def read(self) -> Measurement:
        data = bme280_module.sample(self._bus, self._address, self._calibration)
        return Measurement(
            name=self.name,
            values={
                "temperature_c": data.temperature,
                "humidity_pct": data.humidity,
                "pressure_hpa": data.pressure,
            },
            timestamp=time.time(),
        )
