from __future__ import annotations

from typing import Any

from .base import BaseSensor
from .bh1750 import BH1750Sensor
from .bme280 import BME280Sensor
from .bme680sensor import BME680Sensor
from .ds18b20 import DS18B20Sensor
from .hx711 import HX711Sensor
from .ina3221 import INA3221Sensor

_REGISTRY: dict[str, type[BaseSensor]] = {
    "hx711": HX711Sensor,
    "ds18b20": DS18B20Sensor,
    "bme280": BME280Sensor,
    "bme680": BME680Sensor,
    "bh1750": BH1750Sensor,
    "ina3221": INA3221Sensor,
}


def create_sensor(config: dict[str, Any]) -> BaseSensor:
    sensor_type = config["type"]
    if sensor_type not in _REGISTRY:
        raise ValueError(
            f"Unbekannter Sensor-Typ: {sensor_type!r}. Verfügbar: {list(_REGISTRY)}"
        )
    return _REGISTRY[sensor_type](config)
