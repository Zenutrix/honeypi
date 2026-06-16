from __future__ import annotations
from typing import Any
from .base import BaseExporter
from .local import LocalExporter
from .thingspeak import ThingSpeakExporter
from .influxdb import InfluxDBExporter
from .mqtt import MQTTExporter
from .telegram import TelegramExporter
from .datacake import DatacakeExporter

_REGISTRY: dict[str, type[BaseExporter]] = {
    "local":      LocalExporter,
    "thingspeak": ThingSpeakExporter,
    "influxdb":   InfluxDBExporter,
    "mqtt":       MQTTExporter,
    "telegram":   TelegramExporter,
    "datacake":   DatacakeExporter,
}


def create_exporters(config: dict[str, dict[str, Any]]) -> list[BaseExporter]:
    return [
        _REGISTRY[name](cfg)
        for name, cfg in config.items()
        if cfg.get("enabled", False) and name in _REGISTRY
    ]
