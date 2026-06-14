from __future__ import annotations
from .base import BaseSensor
from .dummy import DummySensor
from .hx711 import HX711Sensor
from .ds18b20 import DS18B20Sensor
from .bme280 import BME280Sensor

_REGISTRY: dict[str, type[BaseSensor]] = {
    "dummy": DummySensor,
    "hx711": HX711Sensor,
    "ds18b20": DS18B20Sensor,
    "bme280": BME280Sensor,
}


def create_sensor(config: dict) -> BaseSensor:
    sensor_type = config["type"]
    if sensor_type not in _REGISTRY:
        raise ValueError(f"Unknown sensor type: {sensor_type!r}")
    return _REGISTRY[sensor_type](config)
