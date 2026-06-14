from __future__ import annotations
from .base import BaseSensor
from .hx711 import HX711Sensor
from .ds18b20 import DS18B20Sensor
from .bme280 import BME280Sensor
from .dht22 import DHT22Sensor
from .sht31 import SHT31Sensor
from .aht10 import AHT10Sensor
from .bme680sensor import BME680Sensor
from .bh1750 import BH1750Sensor
from .ads1115 import ADS1115Sensor

_REGISTRY: dict[str, type[BaseSensor]] = {
    # Weight
    "hx711": HX711Sensor,
    # Temperature (1-wire)
    "ds18b20": DS18B20Sensor,
    # Temperature + Humidity
    "dht11": DHT22Sensor,
    "dht22": DHT22Sensor,
    "sht31": SHT31Sensor,
    "sht25": SHT31Sensor,  # same protocol
    "aht10": AHT10Sensor,
    "aht20": AHT10Sensor,  # same protocol
    # Temperature + Humidity + Pressure
    "bme280": BME280Sensor,
    # Temperature + Humidity + Pressure + Gas
    "bme680": BME680Sensor,
    # Light
    "bh1750": BH1750Sensor,
    # ADC / Battery voltage
    "ads1115": ADS1115Sensor,
}


def create_sensor(config: dict) -> BaseSensor:
    sensor_type = config["type"]
    if sensor_type not in _REGISTRY:
        raise ValueError(f"Unknown sensor type: {sensor_type!r}. Available: {list(_REGISTRY)}")
    return _REGISTRY[sensor_type](config)
