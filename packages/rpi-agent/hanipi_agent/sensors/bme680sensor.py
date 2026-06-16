from __future__ import annotations

import time
from typing import Any

from .base import BaseSensor, Measurement

try:
    import bme680  # type: ignore[import-not-found]

    _HW_AVAILABLE = True
except ImportError:
    _HW_AVAILABLE = False


class BME680Sensor(BaseSensor):
    """BME680 environmental sensor: temperature, humidity, pressure, gas resistance."""

    def _configure(self, config: dict[str, Any]) -> None:
        if not _HW_AVAILABLE:
            return
        address = config.get("i2c_address", bme680.I2C_ADDR_PRIMARY)
        self._sensor = bme680.BME680(address)
        self._sensor.set_humidity_oversample(bme680.OS_2X)
        self._sensor.set_pressure_oversample(bme680.OS_4X)
        self._sensor.set_temperature_oversample(bme680.OS_8X)
        self._sensor.set_filter(bme680.FILTER_SIZE_3)
        self._sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)
        self._sensor.set_gas_heater_temperature(320)
        self._sensor.set_gas_heater_duration(150)
        self._sensor.select_gas_heater_profile(0)

    def read(self) -> Measurement:
        if not _HW_AVAILABLE:
            raise RuntimeError("bme680 package not available")
        if not self._sensor.get_sensor_data():
            raise RuntimeError("BME680 data not ready — retry next cycle")
        values: dict[str, float] = {
            "temperature_c": round(self._sensor.data.temperature, 2),
            "humidity_pct": round(self._sensor.data.humidity, 2),
            "pressure_hpa": round(self._sensor.data.pressure, 2),
        }
        if self._sensor.data.heat_stable:
            values["gas_resistance_ohm"] = round(self._sensor.data.gas_resistance, 0)
        return Measurement(name=self.name, values=values, timestamp=time.time())
