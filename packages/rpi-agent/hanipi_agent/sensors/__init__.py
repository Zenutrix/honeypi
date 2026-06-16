from __future__ import annotations
from typing import Any
from .base import BaseSensor
from .hx711 import HX711Sensor
from .ds18b20 import DS18B20Sensor
from .bme280 import BME280Sensor
from .bme680sensor import BME680Sensor
from .bh1750 import BH1750Sensor
from .ads1115 import ADS1115Sensor

_REGISTRY: dict[str, type[BaseSensor]] = {
    "hx711":   HX711Sensor,
    "ds18b20": DS18B20Sensor,
    "bme280":  BME280Sensor,
    "bme680":  BME680Sensor,
    "bh1750":  BH1750Sensor,
    "ads1115": ADS1115Sensor,
}


def create_sensor(config: dict[str, Any]) -> BaseSensor:
    sensor_type = config["type"]
    if sensor_type not in _REGISTRY:
        raise ValueError(
            f"Unbekannter Sensor-Typ: {sensor_type!r}. "
            f"Verfügbar: {list(_REGISTRY)}"
        )
    return _REGISTRY[sensor_type](config)
